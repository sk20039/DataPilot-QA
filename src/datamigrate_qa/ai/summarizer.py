"""AI run summarizer — executive-level migration health report."""
from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel

from datamigrate_qa.ai.client import get_client

_MODEL = "claude-haiku-4-5"

_SYSTEM = """You are a senior data migration QA engineer. Your job is to review migration
validation results and produce an executive-level health report.

You MUST respond with valid JSON only — no markdown, no explanation outside the JSON.
"""

_SCHEMA = """{
  "overall_status": "<PASS | FAIL | CAUTION>",
  "risk_score": <integer 0-100, where 100 is maximum risk>,
  "headline": "<one-line migration health statement>",
  "key_findings": ["<finding 1>", "<finding 2>"],
  "patterns": ["<systematic issue description if any>"],
  "recommendation": "<Go | No-Go | Investigate further>",
  "details": "<2-3 paragraph narrative>"
}"""


class RunSummary(BaseModel):
    overall_status: Literal["PASS", "FAIL", "CAUTION"]
    risk_score: int
    headline: str
    key_findings: list[str]
    patterns: list[str]
    recommendation: Literal["Go", "No-Go", "Investigate further"]
    details: str


def summarize_run(
    report_data: dict[str, Any],
    source_dialect: str = "",
    target_dialect: str = "",
) -> RunSummary:
    """Generate an AI run summary from a run report dict.

    Args:
        report_data: The report dict stored in _runs (has total/passed/failed/results etc).
        source_dialect: e.g. 'postgresql'
        target_dialect: e.g. 'snowflake'
    """
    client = get_client()

    results = report_data.get("results", [])
    # Summarize by category to reduce token usage
    category_summary: dict[str, dict[str, int]] = {}
    for r in results:
        cat = r.get("category", "unknown")
        status = r.get("status", "UNKNOWN")
        if cat not in category_summary:
            category_summary[cat] = {"PASS": 0, "FAIL": 0, "ERROR": 0, "SKIPPED": 0}
        category_summary[cat][status] = category_summary[cat].get(status, 0) + 1

    # Collect sample failure descriptions (up to 5)
    failure_samples = [
        {
            "category": r.get("category", ""),
            "description": r.get("description", ""),
            "status": r.get("status", ""),
            "diff": (r.get("diff", "") or "")[:200],
            "error": (r.get("error_message", "") or "")[:200],
        }
        for r in results
        if r.get("status") in ("FAIL", "ERROR")
    ][:5]

    dialect_ctx = f"Migration: {source_dialect} → {target_dialect}. " if source_dialect else ""

    context = {
        "dialect_context": dialect_ctx,
        "summary_counts": {
            "total": report_data.get("total", 0),
            "passed": report_data.get("passed", 0),
            "failed": report_data.get("failed", 0),
            "errors": report_data.get("errors", 0),
            "skipped": report_data.get("skipped", 0),
        },
        "results_by_category": category_summary,
        "failure_samples": failure_samples,
    }

    user_prompt = (
        f"Review this migration validation run and produce a health report.\n\n"
        f"Run context:\n{json.dumps(context, indent=2)}\n\n"
        f"Respond ONLY with JSON matching this schema:\n{_SCHEMA}"
    )

    response = client.messages.create(
        model=_MODEL,
        max_tokens=2048,
        system=_SYSTEM,
        messages=[{"role": "user", "content": user_prompt}],
    )

    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.rsplit("```", 1)[0].strip()

    data = json.loads(raw)
    return RunSummary(
        overall_status=data.get("overall_status", "CAUTION"),
        risk_score=int(data.get("risk_score", 50)),
        headline=data.get("headline", ""),
        key_findings=data.get("key_findings", []),
        patterns=data.get("patterns", []),
        recommendation=data.get("recommendation", "Investigate further"),
        details=data.get("details", ""),
    )
