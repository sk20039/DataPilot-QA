"""Console reporter using Rich."""
from __future__ import annotations

from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

from datamigrate_qa.models import RunReport, TestStatus

console = Console()


def _status_style(status: TestStatus) -> str:
    return {
        TestStatus.PASS: "green",
        TestStatus.FAIL: "red bold",
        TestStatus.ERROR: "yellow bold",
        TestStatus.SKIPPED: "dim",
    }.get(status, "white")


def print_report(report: RunReport) -> None:
    """Print a formatted run report to the console."""
    table = Table(
        title=f"Migration QA Report — Run {report.run_id[:8]}",
        box=box.ROUNDED,
        show_lines=True,
    )
    table.add_column("Category", style="cyan", no_wrap=True)
    table.add_column("Description", max_width=60)
    table.add_column("Status", justify="center")
    table.add_column("Source", justify="right")
    table.add_column("Target", justify="right")
    table.add_column("Diff / Error")

    for result in report.results:
        status_style = _status_style(result.status)
        diff_text = result.diff or result.error_message or ""
        table.add_row(
            result.test_case.category,
            result.test_case.description,
            f"[{status_style}]{result.status.value}[/{status_style}]",
            str(result.source_value) if result.source_value is not None else "—",
            str(result.target_value) if result.target_value is not None else "—",
            diff_text[:80],
        )

    console.print(table)
    console.print(
        f"\n[bold]Summary:[/bold] "
        f"[green]{report.passed} PASS[/green]  "
        f"[red]{report.failed} FAIL[/red]  "
        f"[yellow]{report.errors} ERROR[/yellow]  "
        f"[dim]{report.skipped} SKIPPED[/dim]  "
        f"/ {report.total} total"
    )


def print_ai_section(
    report: RunReport,
    source_dialect: str = "",
    target_dialect: str = "",
) -> None:
    """Run AI analysis on a RunReport and print the results."""
    from datamigrate_qa.ai.client import is_available
    from datamigrate_qa.reporting.json_reporter import _serialize

    if not is_available():
        console.print(
            "\n[yellow]AI analysis skipped:[/yellow] ANTHROPIC_API_KEY not set "
            "or 'anthropic' package not installed (pip install -e '.[ai]')."
        )
        return

    # Build the report dict the same way the backend does
    from dataclasses import asdict
    results_dicts = [
        {
            "id": r.test_case.id,
            "category": r.test_case.category,
            "description": r.test_case.description,
            "source_table": r.test_case.table_pair.source_fqn if r.test_case.table_pair else "",
            "target_table": r.test_case.table_pair.target_fqn if r.test_case.table_pair else "",
            "status": r.status.value,
            "source_value": str(r.source_value) if r.source_value is not None else None,
            "target_value": str(r.target_value) if r.target_value is not None else None,
            "diff": r.diff,
            "duration_seconds": r.duration_seconds,
            "error_message": r.error_message,
        }
        for r in report.results
    ]
    report_dict = {
        "total": report.total,
        "passed": report.passed,
        "failed": report.failed,
        "errors": report.errors,
        "skipped": report.skipped,
        "results": results_dicts,
    }

    print_ai_section_from_dict(report_dict, source_dialect=source_dialect, target_dialect=target_dialect)


def print_ai_section_from_dict(
    report_data: dict[str, Any],
    source_dialect: str = "",
    target_dialect: str = "",
) -> None:
    """Run AI analysis on a report dict and print the results."""
    from datamigrate_qa.ai.summarizer import summarize_run
    from datamigrate_qa.ai.analyst import analyze_failures

    console.print("\n[bold cyan]── AI Analysis ──────────────────────────────────────[/bold cyan]")

    # Run summary
    console.print("[dim]Generating run summary...[/dim]")
    try:
        summary = summarize_run(report_data, source_dialect, target_dialect)
    except Exception as exc:
        console.print(f"[red]AI summary failed:[/red] {exc}")
        summary = None

    if summary:
        status_color = {"PASS": "green", "FAIL": "red", "CAUTION": "yellow"}.get(
            summary.overall_status, "white"
        )
        risk_color = "green" if summary.risk_score < 30 else "yellow" if summary.risk_score < 70 else "red"

        console.print(
            Panel(
                f"[{status_color}]{summary.overall_status}[/{status_color}]  "
                f"Risk: [{risk_color}]{summary.risk_score}/100[/{risk_color}]\n\n"
                f"[bold]{summary.headline}[/bold]\n\n"
                f"{summary.details}\n\n"
                f"[bold]Recommendation:[/bold] {summary.recommendation}",
                title="Migration Health Report",
                border_style="cyan",
            )
        )

        if summary.key_findings:
            console.print("[bold]Key findings:[/bold]")
            for finding in summary.key_findings:
                console.print(f"  • {finding}")

        if summary.patterns:
            console.print("[bold]Patterns:[/bold]")
            for pattern in summary.patterns:
                console.print(f"  • {pattern}")

    # Failure analysis
    failures = [r for r in report_data.get("results", []) if r.get("status") in ("FAIL", "ERROR")]
    if failures:
        console.print(f"\n[dim]Analyzing {len(failures)} failure(s)...[/dim]")
        try:
            analyses = analyze_failures(failures, source_dialect, target_dialect)
        except Exception as exc:
            console.print(f"[red]AI failure analysis failed:[/red] {exc}")
            analyses = {}

        if analyses:
            fail_table = Table(
                title="Failure Analysis",
                box=box.SIMPLE_HEAD,
                show_lines=True,
            )
            fail_table.add_column("Test", max_width=40)
            fail_table.add_column("Likely Cause")
            fail_table.add_column("Severity", justify="center")
            fail_table.add_column("Investigate", max_width=50)

            severity_style = {
                "critical": "red bold",
                "warning": "yellow",
                "informational": "dim",
            }

            # Map test_id → description for display
            id_to_desc = {r.get("id", ""): r.get("description", r.get("id", "")) for r in failures}

            for tid, analysis in analyses.items():
                sev = analysis.severity
                sev_style = severity_style.get(sev, "white")
                investigate_str = "\n".join(f"• {a}" for a in analysis.investigate[:3])
                fail_table.add_row(
                    id_to_desc.get(tid, tid)[:40],
                    analysis.likely_cause,
                    f"[{sev_style}]{sev}[/{sev_style}]",
                    investigate_str,
                )

            console.print(fail_table)
