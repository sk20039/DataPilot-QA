"""Sequential test executor."""
from __future__ import annotations

import logging
import time
from typing import Callable

from datamigrate_qa.connectors.base import Connector
from datamigrate_qa.models import ComparisonStrategy, TestCase, TestResult, TestStatus

logger = logging.getLogger(__name__)


def _compare(
    strategy: ComparisonStrategy,
    source_value: object,
    target_value: object,
    tolerance: float = 0.0,
) -> tuple[bool, str]:
    """Compare two values using the given strategy. Returns (passed, diff)."""
    if strategy == ComparisonStrategy.EXACT:
        if source_value == target_value:
            return True, ""
        return False, f"source={source_value!r} target={target_value!r}"

    if strategy == ComparisonStrategy.NUMERIC_TOLERANCE:
        try:
            sv = float(source_value) if source_value is not None else 0.0
            tv = float(target_value) if target_value is not None else 0.0
            if abs(sv - tv) <= tolerance:
                return True, ""
            return False, f"source={sv} target={tv} diff={abs(sv - tv)} tolerance={tolerance}"
        except (TypeError, ValueError) as exc:
            return False, f"Cannot compare numerically: {exc}"

    if strategy in (ComparisonStrategy.SET_EQUALITY, ComparisonStrategy.HASH_MATCH):
        if source_value == target_value:
            return True, ""
        return False, f"source={source_value!r} != target={target_value!r}"

    return False, f"Unknown strategy: {strategy}"


class SequentialRunner:
    """Runs test cases sequentially against source and target connectors."""

    def __init__(
        self,
        source_connector: Connector,
        target_connector: Connector,
        progress_callback: Callable[[TestResult], None] | None = None,
    ) -> None:
        self._source = source_connector
        self._target = target_connector
        self._progress_callback = progress_callback

    def run(self, test_cases: list[TestCase]) -> list[TestResult]:
        """Execute all test cases and return results."""
        results: list[TestResult] = []

        for test_case in test_cases:
            result = self._run_one(test_case)
            results.append(result)
            if self._progress_callback:
                self._progress_callback(result)

        return results

    def _run_one(self, test_case: TestCase) -> TestResult:
        """Execute a single test case."""
        start = time.monotonic()
        try:
            source_value = self._source.execute_scalar(test_case.source_sql)
            target_value = self._target.execute_scalar(test_case.target_sql)
            passed, diff = _compare(
                test_case.comparison_strategy,
                source_value,
                target_value,
                test_case.tolerance,
            )
            status = TestStatus.PASS if passed else TestStatus.FAIL
            return TestResult(
                test_case=test_case,
                status=status,
                source_value=source_value,
                target_value=target_value,
                diff=diff,
                duration_seconds=time.monotonic() - start,
            )
        except Exception as exc:
            logger.exception("Error executing test case %s", test_case.id)
            return TestResult(
                test_case=test_case,
                status=TestStatus.ERROR,
                error_message=str(exc),
                duration_seconds=time.monotonic() - start,
            )
