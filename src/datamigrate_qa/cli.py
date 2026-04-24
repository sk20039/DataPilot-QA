"""CLI entry point using Typer."""
from __future__ import annotations

import logging
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

import typer

app = typer.Typer(
    name="datamigrate-qa",
    help="Automated data migration QA tool.",
    add_completion=False,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


@app.command()
def run(
    config: Path = typer.Option(..., "--config", "-c", help="Path to YAML config file"),
    workers: Optional[int] = typer.Option(None, "--workers", "-w", help="Parallel workers (default: from config)"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose logging"),
    ai: bool = typer.Option(False, "--ai", help="Append AI summary and failure analysis after run"),
) -> None:
    """Run the migration QA test suite."""
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Lazy imports to keep startup fast
    from datamigrate_qa.config.loader import load_config
    from datamigrate_qa.connectors.registry import get_connector
    from datamigrate_qa.introspection.schema_inspector import inspect_tables
    from datamigrate_qa.mapping.auto_mapper import build_mapping
    from datamigrate_qa.generators.row_count import RowCountGenerator
    from datamigrate_qa.generators.schema_validator import SchemaValidatorGenerator
    from datamigrate_qa.generators.field_match import FieldMatchGenerator
    from datamigrate_qa.generators.null_duplicate import NullDuplicateGenerator
    from datamigrate_qa.generators.aggregate_recon import AggregateReconGenerator
    from datamigrate_qa.generators.base import GeneratorConfig
    from datamigrate_qa.executor.runner import SequentialRunner
    from datamigrate_qa.models import RunReport
    from datamigrate_qa.reporting.console_reporter import print_report, print_ai_section
    from datamigrate_qa.reporting.json_reporter import write_json_report
    from datamigrate_qa.reporting.html_reporter import write_html_report

    typer.echo(f"Loading config from {config}")
    try:
        app_config = load_config(config)
    except Exception as exc:
        typer.echo(f"ERROR loading config: {exc}", err=True)
        raise typer.Exit(code=2)

    app_config.run_id = str(uuid.uuid4())
    if workers is not None:
        app_config.max_workers = workers

    report = RunReport(
        run_id=app_config.run_id,
        config_path=str(config),
        started_at=datetime.utcnow(),
    )

    typer.echo("Connecting to source and target...")
    source_connector = get_connector(app_config.source)
    target_connector = get_connector(app_config.target)

    try:
        source_connector.connect()
        target_connector.connect()
    except Exception as exc:
        typer.echo(f"ERROR connecting: {exc}", err=True)
        raise typer.Exit(code=2)

    try:
        typer.echo("Introspecting schemas...")
        inspection = inspect_tables(source_connector, target_connector, app_config.tables)
        for w in inspection.warnings:
            typer.echo(f"WARNING: {w}")

        typer.echo("Building column mappings...")
        migration_mapping = build_mapping(
            app_config.tables,
            inspection.source_metadata,
            inspection.target_metadata,
        )
        for w in migration_mapping.warnings:
            typer.echo(f"WARNING: {w}")

        typer.echo("Generating test cases...")
        gen_cfg = app_config.generators
        generators = []
        if gen_cfg.row_count.enabled:
            generators.append((RowCountGenerator(), gen_cfg.row_count))
        if gen_cfg.schema.enabled:
            generators.append((SchemaValidatorGenerator(), gen_cfg.schema))
        if gen_cfg.field_match.enabled:
            generators.append((FieldMatchGenerator(), gen_cfg.field_match))
        if gen_cfg.null_duplicate.enabled:
            generators.append((NullDuplicateGenerator(), gen_cfg.null_duplicate))
        if gen_cfg.aggregate_recon.enabled:
            generators.append((AggregateReconGenerator(), gen_cfg.aggregate_recon))

        all_test_cases = []
        for generator, options in generators:
            cases = generator.generate(migration_mapping, GeneratorConfig(options=options))
            all_test_cases.extend(cases)

        typer.echo(f"Executing {len(all_test_cases)} test cases...")
        runner = SequentialRunner(source_connector, target_connector)
        results = runner.run(all_test_cases)
        report.results = results
        report.finished_at = datetime.utcnow()

        print_report(report)

        if app_config.output.json:
            write_json_report(report, app_config.output.json)
            typer.echo(f"JSON report: {app_config.output.json}")
        if app_config.output.html:
            write_html_report(report, app_config.output.html)
            typer.echo(f"HTML report: {app_config.output.html}")

        if ai:
            print_ai_section(
                report,
                source_dialect=app_config.source.dialect,
                target_dialect=app_config.target.dialect,
            )

    finally:
        source_connector.disconnect()
        target_connector.disconnect()

    if report.errors > 0:
        raise typer.Exit(code=2)
    if report.failed > 0:
        raise typer.Exit(code=1)
    raise typer.Exit(code=0)


@app.command()
def analyze(
    report_file: Path = typer.Option(..., "--report", "-r", help="Path to JSON report file"),
    source_dialect: str = typer.Option("", "--source-dialect", help="Source DB dialect for context"),
    target_dialect: str = typer.Option("", "--target-dialect", help="Target DB dialect for context"),
) -> None:
    """Analyze an existing JSON report with AI."""
    import json

    from datamigrate_qa.ai.client import is_available
    from datamigrate_qa.reporting.console_reporter import print_ai_section_from_dict

    if not is_available():
        typer.echo(
            "ERROR: AI features require ANTHROPIC_API_KEY environment variable "
            "and the 'anthropic' package (pip install -e '.[ai]').",
            err=True,
        )
        raise typer.Exit(code=2)

    if not report_file.exists():
        typer.echo(f"ERROR: Report file not found: {report_file}", err=True)
        raise typer.Exit(code=2)

    try:
        report_data = json.loads(report_file.read_text())
    except Exception as exc:
        typer.echo(f"ERROR reading report: {exc}", err=True)
        raise typer.Exit(code=2)

    typer.echo("Running AI analysis...")
    print_ai_section_from_dict(report_data, source_dialect=source_dialect, target_dialect=target_dialect)


@app.command(name="generate-test")
def generate_test(
    config: Path = typer.Option(..., "--config", "-c", help="Path to YAML config file"),
    prompt: str = typer.Option(..., "--prompt", "-p", help="Natural language test description"),
    table: str = typer.Option("", "--table", "-t", help="Table name to use for schema context"),
) -> None:
    """Generate a custom test case from a natural language description."""
    import yaml

    from datamigrate_qa.ai.client import is_available
    from datamigrate_qa.ai.nl_generator import SchemaContext, generate_test as ai_generate
    from datamigrate_qa.config.loader import load_config
    from datamigrate_qa.connectors.registry import get_connector
    from datamigrate_qa.introspection.schema_inspector import inspect_tables

    if not is_available():
        typer.echo(
            "ERROR: AI features require ANTHROPIC_API_KEY environment variable "
            "and the 'anthropic' package (pip install -e '.[ai]').",
            err=True,
        )
        raise typer.Exit(code=2)

    typer.echo(f"Loading config from {config}")
    try:
        app_config = load_config(config)
    except Exception as exc:
        typer.echo(f"ERROR loading config: {exc}", err=True)
        raise typer.Exit(code=2)

    # Find matching table pair
    table_pair = None
    if table:
        for tp in app_config.tables:
            if table in (tp.source, tp.target, tp.source.split(".")[-1], tp.target.split(".")[-1]):
                table_pair = tp
                break
        if table_pair is None:
            typer.echo(f"WARNING: Table '{table}' not found in config. Generating without schema context.")

    schema_context = None
    if table_pair:
        typer.echo("Connecting to databases for schema introspection...")
        src_conn = get_connector(app_config.source)
        tgt_conn = get_connector(app_config.target)
        try:
            src_conn.connect()
            tgt_conn.connect()
            inspection = inspect_tables(src_conn, tgt_conn, [table_pair])
            src_meta = next(iter(inspection.source_metadata.values()), None)
            tgt_meta = next(iter(inspection.target_metadata.values()), None)
            if src_meta and tgt_meta:
                schema_context = SchemaContext(
                    source_table=src_meta.fqn,
                    target_table=tgt_meta.fqn,
                    source_columns=[
                        {"name": c.name, "type": c.canonical_type.value} for c in src_meta.columns
                    ],
                    target_columns=[
                        {"name": c.name, "type": c.canonical_type.value} for c in tgt_meta.columns
                    ],
                    primary_keys=src_meta.primary_keys,
                )
        except Exception as exc:
            typer.echo(f"WARNING: Could not introspect schema: {exc}")
        finally:
            src_conn.disconnect()
            tgt_conn.disconnect()

    typer.echo("Generating test case with AI...")
    try:
        tc = ai_generate(
            prompt=prompt,
            schema_context=schema_context,
            source_dialect=app_config.source.dialect,
            target_dialect=app_config.target.dialect,
        )
    except Exception as exc:
        typer.echo(f"ERROR: AI generation failed: {exc}", err=True)
        raise typer.Exit(code=2)

    # Print as YAML snippet
    typer.echo("\n# Add this to your config's custom_tests section:\n")
    output = {
        "description": tc.description,
        "source_sql": tc.source_sql,
        "target_sql": tc.target_sql,
        "comparison_strategy": tc.comparison_strategy,
    }
    if tc.comparison_strategy == "NUMERIC_TOLERANCE":
        output["tolerance"] = tc.tolerance
    typer.echo(yaml.dump([output], default_flow_style=False, sort_keys=False))
    typer.echo(f"# Explanation: {tc.explanation}")


if __name__ == "__main__":
    app()
