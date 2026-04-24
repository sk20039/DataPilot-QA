"""Tests for core data models."""
from __future__ import annotations

import pytest
from datamigrate_qa.models import (
    CanonicalType,
    ColumnMetadata,
    ComparisonStrategy,
    RunReport,
    TableMetadata,
    TestCase,
    TestResult,
    TestStatus,
)


def test_table_metadata_fqn() -> None:
    meta = TableMetadata(schema="public", table="orders", columns=[], primary_keys=[])
    assert meta.fqn == "public.orders"


def test_run_report_summary() -> None:
    report = RunReport()
    tc = TestCase(category="row_count")
    report.results = [
        TestResult(test_case=tc, status=TestStatus.PASS),
        TestResult(test_case=tc, status=TestStatus.FAIL),
        TestResult(test_case=tc, status=TestStatus.ERROR),
        TestResult(test_case=tc, status=TestStatus.SKIPPED),
    ]
    assert report.total == 4
    assert report.passed == 1
    assert report.failed == 1
    assert report.errors == 1
    assert report.skipped == 1
    assert not report.all_passed


def test_run_report_all_passed() -> None:
    report = RunReport()
    tc = TestCase(category="row_count")
    report.results = [TestResult(test_case=tc, status=TestStatus.PASS)]
    assert report.all_passed


def test_canonical_types_are_strings() -> None:
    assert CanonicalType.STRING == "STRING"
    assert CanonicalType.INTEGER == "INTEGER"
