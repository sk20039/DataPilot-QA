"""JSON reporter."""
from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from datamigrate_qa.models import RunReport


def _serialize(obj: object) -> object:
    if hasattr(obj, "value"):  # Enum
        return obj.value
    if hasattr(obj, "__dataclass_fields__"):  # dataclass
        return {k: _serialize(v) for k, v in asdict(obj).items()}  # type: ignore[call-overload]
    if isinstance(obj, list):
        return [_serialize(i) for i in obj]
    if isinstance(obj, dict):
        return {k: _serialize(v) for k, v in obj.items()}
    return obj


def write_json_report(report: RunReport, path: str | Path) -> None:
    """Write the run report as JSON."""
    output_path = Path(path)
    data = {
        "run_id": report.run_id,
        "started_at": report.started_at.isoformat(),
        "finished_at": report.finished_at.isoformat() if report.finished_at else None,
        "summary": {
            "total": report.total,
            "passed": report.passed,
            "failed": report.failed,
            "errors": report.errors,
            "skipped": report.skipped,
        },
        "results": [
            {
                "id": r.test_case.id,
                "category": r.test_case.category,
                "description": r.test_case.description,
                "status": r.status.value,
                "source_value": r.source_value,
                "target_value": r.target_value,
                "diff": r.diff,
                "error_message": r.error_message,
                "duration_seconds": r.duration_seconds,
                "source_sql": r.test_case.source_sql,
                "target_sql": r.test_case.target_sql,
            }
            for r in report.results
        ],
    }
    output_path.write_text(json.dumps(data, indent=2, default=str))
