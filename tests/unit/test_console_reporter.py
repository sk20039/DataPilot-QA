"""Tests for console reporter."""
from __future__ import annotations

from io import StringIO

from rich.console import Console

from datamigrate_qa.models import RunReport, TestCase, TestResult, TestStatus
from datamigrate_qa.reporting.console_reporter import print_report


def _make_report(*statuses: TestStatus) -> RunReport:
    report = RunReport()
    for status in statuses:
        tc = TestCase(category="row_count", description=f"Test {status.value}")
        report.results.append(TestResult(test_case=tc, status=status))
    return report


def test_print_report_no_exception() -> None:
    """Ensure print_report runs without exceptions."""
    report = _make_report(TestStatus.PASS, TestStatus.FAIL, TestStatus.ERROR)
    # Redirect output to avoid polluting test output
    import datamigrate_qa.reporting.console_reporter as cr
    original = cr.console
    cr.console = Console(file=StringIO())
    try:
        print_report(report)
    finally:
        cr.console = original


def test_summary_counts() -> None:
    report = _make_report(TestStatus.PASS, TestStatus.PASS, TestStatus.FAIL)
    assert report.passed == 2
    assert report.failed == 1
    assert report.total == 3
