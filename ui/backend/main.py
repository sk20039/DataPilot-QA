"""FastAPI backend for the DataMigrate QA UI."""
from __future__ import annotations

import asyncio
import threading
import uuid
from datetime import datetime
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

app = FastAPI(title="DataMigrate QA API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory run store (local tool, no persistence needed)
_runs: dict[str, dict[str, Any]] = {}
_runs_lock = threading.Lock()


# ── API request/response models ───────────────────────────────────────────────

class ConnectionRequest(BaseModel):
    dialect: str = "postgresql"
    host: str = "localhost"
    port: int = 5432
    database: str = ""
    username: str = ""
    password: str = ""
    schema_name: str | None = None
    account: str | None = None  # Snowflake


class TableEntry(BaseModel):
    source: str
    target: str
    primaryKey: str | None = None


class GeneratorSetting(BaseModel):
    enabled: bool = True
    tolerance: float = 1e-6


class GeneratorsRequest(BaseModel):
    row_count: GeneratorSetting = Field(default_factory=GeneratorSetting)
    schema_check: GeneratorSetting = Field(default_factory=GeneratorSetting)
    field_match: GeneratorSetting = Field(default_factory=GeneratorSetting)
    null_duplicate: GeneratorSetting = Field(default_factory=GeneratorSetting)
    aggregate_recon: GeneratorSetting = Field(default_factory=GeneratorSetting)
    missing_rows: GeneratorSetting = Field(default_factory=lambda: GeneratorSetting(enabled=False))


class CustomTestRequest(BaseModel):
    description: str = ""
    source_sql: str
    target_sql: str
    comparison_strategy: str = "EXACT"
    tolerance: float = 0.0


class RunRequest(BaseModel):
    source: ConnectionRequest
    target: ConnectionRequest
    tables: list[TableEntry]
    generators: GeneratorsRequest = Field(default_factory=GeneratorsRequest)
    max_workers: int = 4
    custom_tests: list[CustomTestRequest] = Field(default_factory=list)


class ExplainResultRequest(BaseModel):
    run_id: str
    test_id: str


class GenerateTestRequest(BaseModel):
    source_conn: ConnectionRequest
    target_conn: ConnectionRequest
    table_pair: TableEntry | None = None
    prompt: str


# ── Helpers ───────────────────────────────────────────────────────────────────

def _build_conn_cfg(req: ConnectionRequest) -> Any:
    from datamigrate_qa.config.models import ConnectionConfig
    return ConnectionConfig(
        dialect=req.dialect,
        host=req.host or None,
        port=req.port or None,
        database=req.database or None,
        username=req.username or None,
        password=req.password or None,
        schema=req.schema_name or None,
        account=req.account or None,
    )


def _result_to_dict(result: Any) -> dict[str, Any]:
    tc = result.test_case
    return {
        "id": tc.id,
        "category": tc.category,
        "description": tc.description,
        "source_table": tc.table_pair.source_fqn if tc.table_pair else "",
        "target_table": tc.table_pair.target_fqn if tc.table_pair else "",
        "status": result.status.value,
        "source_value": str(result.source_value) if result.source_value is not None else None,
        "target_value": str(result.target_value) if result.target_value is not None else None,
        "diff": result.diff,
        "duration_seconds": round(result.duration_seconds, 3),
        "error_message": result.error_message,
    }


def _run_validation(run_id: str, req: RunRequest) -> None:
    """Execute validation pipeline in a background thread."""
    from datamigrate_qa.config.models import TableConfig
    from datamigrate_qa.config.models import GeneratorOptions as DQGeneratorOptions
    from datamigrate_qa.connectors.registry import get_connector
    from datamigrate_qa.introspection.schema_inspector import inspect_tables
    from datamigrate_qa.mapping.auto_mapper import build_mapping
    from datamigrate_qa.generators.row_count import RowCountGenerator
    from datamigrate_qa.generators.schema_validator import SchemaValidatorGenerator
    from datamigrate_qa.generators.field_match import FieldMatchGenerator
    from datamigrate_qa.generators.null_duplicate import NullDuplicateGenerator
    from datamigrate_qa.generators.aggregate_recon import AggregateReconGenerator
    from datamigrate_qa.generators.missing_rows import MissingRowsGenerator
    from datamigrate_qa.generators.base import GeneratorConfig
    from datamigrate_qa.executor.runner import SequentialRunner
    from datamigrate_qa.executor.parallel import ParallelRunner
    from datamigrate_qa.config.models import AppConfig
    from datamigrate_qa.models import RunReport, TestCase, ComparisonStrategy

    def update(patch: dict[str, Any]) -> None:
        with _runs_lock:
            _runs[run_id].update(patch)

    try:
        update({"progress": "Connecting to databases..."})
        src_cfg = _build_conn_cfg(req.source)
        tgt_cfg = _build_conn_cfg(req.target)
        tables = [
            TableConfig(
                source=t.source,
                target=t.target,
                primary_key_override=[c.strip() for c in t.primaryKey.split(",") if c.strip()] if t.primaryKey else None,
            )
            for t in req.tables
        ]

        src_conn = get_connector(src_cfg)
        tgt_conn = get_connector(tgt_cfg)
        src_conn.connect()
        tgt_conn.connect()

        try:
            update({"progress": "Introspecting schemas..."})
            src_schema = req.source.schema_name or "public"
            tgt_schema = req.target.schema_name or "public"
            inspection = inspect_tables(src_conn, tgt_conn, tables, src_schema, tgt_schema)

            update({"progress": "Building column mappings..."})
            mapping = build_mapping(tables, inspection.source_metadata, inspection.target_metadata)

            # Apply user-specified primary key overrides
            pk_overrides = {t.source: t.primary_key_override for t in tables if t.primary_key_override}
            for tm in mapping.table_mappings:
                table_name = tm.source_fqn.split(".")[-1]
                if table_name in pk_overrides:
                    tm.primary_keys = pk_overrides[table_name]

            update({"progress": "Generating test cases..."})
            g = req.generators
            generators: list[tuple[Any, Any]] = []
            if g.row_count.enabled:
                generators.append((RowCountGenerator(), DQGeneratorOptions(enabled=True, tolerance=g.row_count.tolerance)))
            if g.schema_check.enabled:
                generators.append((SchemaValidatorGenerator(), DQGeneratorOptions(enabled=True)))
            if g.field_match.enabled:
                generators.append((FieldMatchGenerator(), DQGeneratorOptions(enabled=True)))
            if g.null_duplicate.enabled:
                generators.append((NullDuplicateGenerator(), DQGeneratorOptions(enabled=True)))
            if g.aggregate_recon.enabled:
                generators.append((AggregateReconGenerator(), DQGeneratorOptions(enabled=True, tolerance=g.aggregate_recon.tolerance)))
            if g.missing_rows.enabled:
                generators.append((MissingRowsGenerator(), DQGeneratorOptions(enabled=True)))

            all_cases = []
            for gen, opts in generators:
                all_cases.extend(gen.generate(mapping, GeneratorConfig(options=opts)))

            for ct in req.custom_tests:
                try:
                    strategy = ComparisonStrategy(ct.comparison_strategy)
                except ValueError:
                    strategy = ComparisonStrategy.EXACT
                all_cases.append(TestCase(
                    category="custom",
                    table_pair=None,
                    source_sql=ct.source_sql,
                    target_sql=ct.target_sql,
                    comparison_strategy=strategy,
                    tolerance=ct.tolerance,
                    description=ct.description,
                ))

            update({"progress": f"Running {len(all_cases)} test cases..."})
            if req.max_workers > 1:
                app_cfg = AppConfig(source=src_cfg, target=tgt_cfg, max_workers=req.max_workers)
                runner = ParallelRunner(app_cfg, max_workers=req.max_workers)
            else:
                runner = SequentialRunner(src_conn, tgt_conn)
            results = runner.run(all_cases)

            report = RunReport(
                run_id=run_id,
                started_at=datetime.utcnow(),
                finished_at=datetime.utcnow(),
                results=results,
            )
            update({
                "status": "completed",
                "progress": "Complete",
                "source_dialect": req.source.dialect,
                "target_dialect": req.target.dialect,
                "report": {
                    "run_id": run_id,
                    "total": report.total,
                    "passed": report.passed,
                    "failed": report.failed,
                    "errors": report.errors,
                    "skipped": report.skipped,
                    "all_passed": report.all_passed,
                    "warnings": inspection.warnings + mapping.warnings,
                    "results": [_result_to_dict(r) for r in results],
                },
            })

        finally:
            src_conn.disconnect()
            tgt_conn.disconnect()

    except Exception as exc:
        update({"status": "error", "error": str(exc), "progress": "Failed"})


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.post("/api/connections/test")
async def test_connection(conn: ConnectionRequest) -> dict[str, Any]:
    """Test a DB connection and return available tables."""
    try:
        from datamigrate_qa.connectors.registry import get_connector
        cfg = _build_conn_cfg(conn)
        connector = get_connector(cfg)
        connector.connect()
        _default_schema = {
            "postgresql": "public",
            "snowflake": "PUBLIC",
            "oracle": conn.username.upper(),
            "mysql": conn.database,
            "mariadb": conn.database,
        }
        schema = conn.schema_name or _default_schema.get(conn.dialect, "public")
        tables = connector.list_tables(schema)
        connector.disconnect()
        return {"ok": True, "tables": sorted(tables)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@app.post("/api/runs")
async def start_run(req: RunRequest) -> dict[str, str]:
    """Start a validation run and return its ID."""
    run_id = str(uuid.uuid4())
    with _runs_lock:
        _runs[run_id] = {"status": "running", "progress": "Starting...", "report": None, "error": None}
    thread = threading.Thread(target=_run_validation, args=(run_id, req), daemon=True)
    thread.start()
    return {"run_id": run_id}


@app.get("/api/runs/{run_id}")
async def get_run(run_id: str) -> dict[str, Any]:
    """Poll for run status and results."""
    with _runs_lock:
        run = _runs.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return {"run_id": run_id, **run}


# ── AI Endpoints ──────────────────────────────────────────────────────────────

def _check_ai_available() -> None:
    """Raise HTTPException 503 if AI is not available."""
    from datamigrate_qa.ai.client import is_available
    if not is_available():
        raise HTTPException(
            status_code=503,
            detail="AI features require ANTHROPIC_API_KEY environment variable and the 'anthropic' package.",
        )


@app.post("/api/ai/analyze-run/{run_id}")
async def analyze_run(run_id: str) -> dict[str, Any]:
    """Run AI summary + failure analysis for a completed run."""
    _check_ai_available()

    with _runs_lock:
        run = _runs.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    if run.get("status") != "completed":
        raise HTTPException(status_code=400, detail="Run is not yet completed")

    report = run.get("report")
    if not report:
        raise HTTPException(status_code=400, detail="Run has no report data")

    source_dialect = run.get("source_dialect", "")
    target_dialect = run.get("target_dialect", "")

    def do_analysis() -> dict[str, Any]:
        from datamigrate_qa.ai.summarizer import summarize_run
        from datamigrate_qa.ai.analyst import analyze_failures

        summary = summarize_run(report, source_dialect, target_dialect)
        failures = [r for r in report.get("results", []) if r.get("status") in ("FAIL", "ERROR")]
        analyses = analyze_failures(failures, source_dialect, target_dialect) if failures else {}

        return {
            "summary": summary.model_dump(),
            "analyses": {tid: a.model_dump() for tid, a in analyses.items()},
        }

    loop = asyncio.get_event_loop()
    try:
        result = await loop.run_in_executor(None, do_analysis)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"AI analysis failed: {exc}")

    return result


@app.post("/api/ai/explain-result")
async def explain_result(req: ExplainResultRequest) -> dict[str, Any]:
    """Lazily explain a single FAIL/ERROR result."""
    _check_ai_available()

    with _runs_lock:
        run = _runs.get(req.run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")

    report = run.get("report")
    if not report:
        raise HTTPException(status_code=400, detail="Run has no report data")

    result = next(
        (r for r in report.get("results", []) if r.get("id") == req.test_id),
        None,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Test result not found")

    source_dialect = run.get("source_dialect", "")
    target_dialect = run.get("target_dialect", "")

    def do_explain() -> dict[str, Any]:
        from datamigrate_qa.ai.analyst import analyze_one
        analysis = analyze_one(result, source_dialect, target_dialect)
        return analysis.model_dump()

    loop = asyncio.get_event_loop()
    try:
        analysis = await loop.run_in_executor(None, do_explain)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"AI analysis failed: {exc}")

    return analysis


@app.post("/api/ai/generate-test")
async def generate_test(req: GenerateTestRequest) -> dict[str, Any]:
    """Generate a custom test case from a natural language prompt."""
    _check_ai_available()

    def do_generate() -> dict[str, Any]:
        from datamigrate_qa.ai.nl_generator import SchemaContext, generate_test as ai_generate
        from datamigrate_qa.connectors.registry import get_connector
        from datamigrate_qa.introspection.schema_inspector import inspect_tables
        from datamigrate_qa.config.models import TableConfig

        schema_context = None
        if req.table_pair:
            src_cfg = _build_conn_cfg(req.source_conn)
            tgt_cfg = _build_conn_cfg(req.target_conn)
            src_conn = get_connector(src_cfg)
            tgt_conn = get_connector(tgt_cfg)
            try:
                src_conn.connect()
                tgt_conn.connect()
                table_cfg = TableConfig(source=req.table_pair.source, target=req.table_pair.target)
                inspection = inspect_tables(src_conn, tgt_conn, [table_cfg])
                src_meta = next(iter(inspection.source_metadata.values()), None)
                tgt_meta = next(iter(inspection.target_metadata.values()), None)
                if src_meta and tgt_meta:
                    schema_context = SchemaContext(
                        source_table=src_meta.fqn,
                        target_table=tgt_meta.fqn,
                        source_columns=[
                            {"name": c.name, "type": c.canonical_type.value}
                            for c in src_meta.columns
                        ],
                        target_columns=[
                            {"name": c.name, "type": c.canonical_type.value}
                            for c in tgt_meta.columns
                        ],
                        primary_keys=src_meta.primary_keys,
                    )
            finally:
                src_conn.disconnect()
                tgt_conn.disconnect()

        tc = ai_generate(
            prompt=req.prompt,
            schema_context=schema_context,
            source_dialect=req.source_conn.dialect,
            target_dialect=req.target_conn.dialect,
        )
        return tc.model_dump()

    loop = asyncio.get_event_loop()
    try:
        result = await loop.run_in_executor(None, do_generate)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"AI generation failed: {exc}")

    return result
