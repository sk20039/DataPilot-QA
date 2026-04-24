"""AI failure analyst — per-result root cause analysis."""
from __future__ import annotations

import json
from typing import Literal

from pydantic import BaseModel

from datamigrate_qa.ai.client import get_client

_MODEL = "claude-haiku-4-5"

_SYSTEM = """You are a data migration QA analyst. Your job is to analyze failed or errored
test results from a database migration validation run and identify the root cause of each failure.

You MUST respond with valid JSON only — no markdown, no explanation outside the JSON.
"""

_BATCH_SCHEMA = """{
  "analyses": [
    {
      "test_id": "<string — exact test ID from input>",
      "likely_cause": "<short label, e.g. 'Row count mismatch due to duplicate key'>",
      "explanation": "<2-3 sentence plain-English explanation>",
      "investigate": ["<action item 1>", "<action item 2>"],
      "severity": "<one of: critical | warning | informational>"
    }
  ]
}"""


class FailureAnalysis(BaseModel):
    likely_cause: str
    explanation: str
    investigate: list[str]
    severity: Literal["critical", "warning", "informational"]


def analyze_failures(
    results: list[dict],
    source_dialect: str = "",
    target_dialect: str = "",
) -> dict[str, FailureAnalysis]:
    """Analyze a batch of FAIL/ERROR results in a single API call.

    Args:
        results: List of result dicts (from _result_to_dict or JSON report).
        source_dialect: e.g. 'postgresql'
        target_dialect: e.g. 'snowflake'

    Returns:
        Dict mapping test_id → FailureAnalysis.
    """
    if not results:
        return {}

    client = get_client()
    dialect_ctx = (
        f"Migration: {source_dialect} → {target_dialect}. " if source_dialect else ""
    )

    failures_json = json.dumps(
        [
            {
                "test_id": r.get("id", ""),
                "category": r.get("category", ""),
                "description": r.get("description", ""),
                "source_table": r.get("source_table", ""),
                "status": r.get("status", ""),
                "source_value": r.get("source_value"),
                "target_value": r.get("target_value"),
                "diff": r.get("diff", ""),
                "error_message": r.get("error_message", ""),
            }
            for r in results
        ],
        indent=2,
    )

    user_prompt = (
        f"{dialect_ctx}Here are the failed/errored test results:\n\n"
        f"{failures_json}\n\n"
        f"Analyze EACH result and respond ONLY with JSON matching this schema:\n"
        f"{_BATCH_SCHEMA}"
    )

    response = client.messages.create(
        model=_MODEL,
        max_tokens=4096,
        system=_SYSTEM,
        messages=[{"role": "user", "content": user_prompt}],
    )

    raw = response.content[0].text.strip()
    # Strip markdown code fences if present
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.rsplit("```", 1)[0].strip()

    data = json.loads(raw)
    out: dict[str, FailureAnalysis] = {}
    for item in data.get("analyses", []):
        tid = item.get("test_id", "")
        if tid:
            out[tid] = FailureAnalysis(
                likely_cause=item.get("likely_cause", ""),
                explanation=item.get("explanation", ""),
                investigate=item.get("investigate", []),
                severity=item.get("severity", "informational"),
            )
    return out


def analyze_one(
    result: dict,
    source_dialect: str = "",
    target_dialect: str = "",
) -> FailureAnalysis:
    """Analyze a single FAIL/ERROR result."""
    analyses = analyze_failures([result], source_dialect, target_dialect)
    tid = result.get("id", "")
    if tid in analyses:
        return analyses[tid]
    # Fallback if test_id not matched
    return next(iter(analyses.values())) if analyses else FailureAnalysis(
        likely_cause="Unknown",
        explanation="Could not determine the cause of this failure.",
        investigate=["Review source and target data manually."],
        severity="informational",
    )
