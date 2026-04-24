"""Core data models for the Data Migration QA tool."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class CanonicalType(str, Enum):
    """Normalized database types across dialects."""
    STRING = "STRING"
    INTEGER = "INTEGER"
    FLOAT = "FLOAT"
    NUMERIC = "NUMERIC"
    BOOLEAN = "BOOLEAN"
    DATE = "DATE"
    TIMESTAMP = "TIMESTAMP"
    TIMESTAMP_TZ = "TIMESTAMP_TZ"
    BINARY = "BINARY"
    JSON = "JSON"
    ARRAY = "ARRAY"
    UNKNOWN = "UNKNOWN"


class ComparisonStrategy(str, Enum):
    """Strategy for comparing test results."""
    EXACT = "EXACT"
    NUMERIC_TOLERANCE = "NUMERIC_TOLERANCE"
    SET_EQUALITY = "SET_EQUALITY"
    HASH_MATCH = "HASH_MATCH"


class TestStatus(str, Enum):
    """Status of a test result."""
    PASS = "PASS"
    FAIL = "FAIL"
    ERROR = "ERROR"
    SKIPPED = "SKIPPED"


@dataclass
class ColumnMetadata:
    """Metadata for a single column."""
    name: str
    canonical_type: CanonicalType
    is_nullable: bool
    ordinal_position: int
    native_type: str


@dataclass
class TableMetadata:
    """Metadata for a single table."""
    schema: str
    table: str
    columns: list[ColumnMetadata]
    primary_keys: list[str]

    @property
    def fqn(self) -> str:
        return f"{self.schema}.{self.table}"


@dataclass
class TablePair:
    """A source/target table pair."""
    source_fqn: str
    target_fqn: str


@dataclass
class TestCase:
    """A single test case to be executed."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    category: str = ""
    table_pair: TablePair | None = None
    source_sql: str = ""
    target_sql: str = ""
    comparison_strategy: ComparisonStrategy = ComparisonStrategy.EXACT
    tolerance: float = 0.0
    description: str = ""


@dataclass
class TestResult:
    """Result of executing a single test case."""
    test_case: TestCase
    status: TestStatus
    source_value: Any = None
    target_value: Any = None
    diff: str = ""
    duration_seconds: float = 0.0
    error_message: str = ""


@dataclass
class RunReport:
    """Full report for a migration QA run."""
    run_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    started_at: datetime = field(default_factory=datetime.utcnow)
    finished_at: datetime | None = None
    results: list[TestResult] = field(default_factory=list)
    config_path: str = ""

    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def passed(self) -> int:
        return sum(1 for r in self.results if r.status == TestStatus.PASS)

    @property
    def failed(self) -> int:
        return sum(1 for r in self.results if r.status == TestStatus.FAIL)

    @property
    def errors(self) -> int:
        return sum(1 for r in self.results if r.status == TestStatus.ERROR)

    @property
    def skipped(self) -> int:
        return sum(1 for r in self.results if r.status == TestStatus.SKIPPED)

    @property
    def all_passed(self) -> bool:
        return self.failed == 0 and self.errors == 0
