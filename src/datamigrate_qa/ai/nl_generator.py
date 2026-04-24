"""Natural language → SQL test case generator."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel

from datamigrate_qa.ai.client import get_client

_MODEL = "claude-sonnet-4-6"

_SYSTEM = """You are an expert SQL developer specializing in data migration validation.
Given a natural language description of a test, generate the corresponding SQL queries for
both source and target databases.

Rules:
- Write SELECT-only queries (no INSERT, UPDATE, DELETE, DROP, CREATE, ALTER, TRUNCATE).
- Adapt syntax for the specified dialects (e.g. LIMIT vs ROWNUM for Oracle, :: vs CAST).
- Return deterministic, aggregate-level queries where possible (not row-level scans).
- The source and target SQL should test the same logical assertion.

When schema context is provided, use it intelligently:
- NUMERIC columns (FLOAT, NUMERIC, INTEGER): use SUM()/AVG() aggregates and prefer
  NUMERIC_TOLERANCE as the comparison strategy for financial or measured values.
- DATE/TIMESTAMP columns: use DATE_TRUNC (PostgreSQL/Snowflake) or TRUNC (Oracle) to
  normalise granularity; cast to DATE when comparing across dialects with different
  timezone defaults.
- Primary key columns: use COUNT(DISTINCT <pk>) for completeness checks; a mismatch
  indicates rows were dropped or duplicated during migration.
- FK-like columns (names ending in _id): suggest referential integrity assertions such as
  COUNT(DISTINCT <fk_col>) or a NOT IN / EXCEPT check when the prompt requests it.

You MUST respond with valid JSON only — no markdown, no explanation outside the JSON.
"""

_SCHEMA = """{
  "source_sql": "<SELECT query for source database>",
  "target_sql": "<SELECT query for target database>",
  "comparison_strategy": "<EXACT | NUMERIC_TOLERANCE>",
  "tolerance": <float, only relevant if NUMERIC_TOLERANCE, e.g. 0.01>,
  "description": "<short auto-generated test description>",
  "explanation": "<why this SQL achieves the stated goal>"
}"""

_UNSAFE = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|TRUNCATE|GRANT|REVOKE|EXEC|EXECUTE)\b",
    re.IGNORECASE,
)


_NUMERIC_TYPES = {"FLOAT", "NUMERIC", "INTEGER"}
_DATE_TYPES = {"DATE", "TIMESTAMP", "TIMESTAMP_TZ"}


@dataclass
class SchemaContext:
    source_table: str
    target_table: str
    source_columns: list[dict[str, Any]]  # [{"name": ..., "type": ...}]
    target_columns: list[dict[str, Any]]
    primary_keys: list[str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.primary_keys is None:
            self.primary_keys = []


def _build_schema_hints(ctx: SchemaContext) -> str:
    """Analyse column types and return a human-readable hints block for the prompt."""
    cols = ctx.source_columns  # use source as canonical; target should mirror it

    numeric_cols = [c["name"] for c in cols if c.get("type") in _NUMERIC_TYPES]
    date_cols = [c["name"] for c in cols if c.get("type") in _DATE_TYPES]
    fk_cols = [
        c["name"] for c in cols
        if c["name"].lower().endswith("_id") and c["name"].lower() != "id"
    ]
    pk_cols = ctx.primary_keys or [c["name"] for c in cols if c["name"].lower() == "id"]

    lines: list[str] = ["Schema intelligence (apply these when writing SQL):"]

    if pk_cols:
        lines.append(
            f"  • Primary key(s): {pk_cols} — use COUNT(DISTINCT ...) for row completeness checks."
        )
    if numeric_cols:
        lines.append(
            f"  • Numeric columns: {numeric_cols} — use SUM()/AVG() aggregates; "
            "prefer NUMERIC_TOLERANCE strategy for financial/measured values."
        )
    if date_cols:
        lines.append(
            f"  • Date/timestamp columns: {date_cols} — normalise with DATE_TRUNC (PG/Snowflake) "
            "or TRUNC (Oracle); cast to DATE when comparing across dialects."
        )
    if fk_cols:
        lines.append(
            f"  • FK-like columns: {fk_cols} — check referential integrity with "
            "COUNT(DISTINCT ...) or an EXCEPT/MINUS query if the prompt requests it."
        )
    if not any([pk_cols, numeric_cols, date_cols, fk_cols]):
        lines.append("  • No special column types detected — write a generic COUNT(*) assertion.")

    return "\n".join(lines)


class GeneratedTestCase(BaseModel):
    source_sql: str
    target_sql: str
    comparison_strategy: Literal["EXACT", "NUMERIC_TOLERANCE"]
    tolerance: float
    description: str
    explanation: str


def _is_safe_sql(sql: str) -> bool:
    """Return True if the SQL contains no DDL/DML statements."""
    return not _UNSAFE.search(sql)


def generate_test(
    prompt: str,
    schema_context: SchemaContext | None = None,
    source_dialect: str = "postgresql",
    target_dialect: str = "postgresql",
) -> GeneratedTestCase:
    """Generate a TestCase from a natural language prompt.

    Args:
        prompt: User's description, e.g. "ensure revenue totals match within 1%"
        schema_context: Optional column info for the target table pair.
        source_dialect: Source DB dialect (postgresql, snowflake, oracle).
        target_dialect: Target DB dialect.

    Returns:
        GeneratedTestCase with validated, read-only SQL.

    Raises:
        ValueError: If generated SQL contains unsafe statements.
    """
    client = get_client()

    schema_section = ""
    if schema_context:
        hints = _build_schema_hints(schema_context)
        schema_section = (
            f"\nTable context:\n"
            f"  Source table: {schema_context.source_table}\n"
            f"  Target table: {schema_context.target_table}\n"
            f"  Source columns: {json.dumps(schema_context.source_columns)}\n"
            f"  Target columns: {json.dumps(schema_context.target_columns)}\n\n"
            f"{hints}\n"
        )

    user_prompt = (
        f"Source dialect: {source_dialect}\n"
        f"Target dialect: {target_dialect}\n"
        f"{schema_section}\n"
        f"Test description: {prompt}\n\n"
        f"Generate SQL queries for both source and target that validate this assertion.\n"
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
    tc = GeneratedTestCase(
        source_sql=data.get("source_sql", ""),
        target_sql=data.get("target_sql", ""),
        comparison_strategy=data.get("comparison_strategy", "EXACT"),
        tolerance=float(data.get("tolerance", 0.0)),
        description=data.get("description", prompt[:100]),
        explanation=data.get("explanation", ""),
    )

    if not _is_safe_sql(tc.source_sql) or not _is_safe_sql(tc.target_sql):
        raise ValueError(
            "Generated SQL contains unsafe statements (DDL/DML). "
            "Please refine your prompt to request read-only assertions."
        )

    return tc
