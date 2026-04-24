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
        if test_case.category == "missing_rows":
            return self._run_missing_rows(test_case)

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

    def _run_missing_rows(self, test_case: TestCase) -> TestResult:
        """Fetch PKs from both sides, diff in Python, report missing IDs."""
        MAX_ROWS = 10_000
        SAMPLE_SIZE = 100
        start = time.monotonic()
        try:
            src_keys: set[tuple[object, ...]] = set()
            for chunk in self._source.execute_query(test_case.source_sql):
                for row in chunk:
                    src_keys.add(tuple(row.values()))
                    if len(src_keys) >= MAX_ROWS:
                        break
                if len(src_keys) >= MAX_ROWS:
                    break

            tgt_keys: set[tuple[object, ...]] = set()
            for chunk in self._target.execute_query(test_case.target_sql):
                for row in chunk:
                    tgt_keys.add(tuple(row.values()))
                    if len(tgt_keys) >= MAX_ROWS:
                        break
                if len(tgt_keys) >= MAX_ROWS:
                    break

            missing_in_target = src_keys - tgt_keys
            extra_in_target = tgt_keys - src_keys

            if not missing_in_target and not extra_in_target:
                return TestResult(
                    test_case=test_case,
                    status=TestStatus.PASS,
                    source_value=len(src_keys),
                    target_value=len(tgt_keys),
                    duration_seconds=time.monotonic() - start,
                )

            diff_parts: list[str] = []
            if missing_in_target:
                sample = sorted(missing_in_target)[:SAMPLE_SIZE]
                ids = ", ".join(
                    str(pk[0]) if len(pk) == 1 else str(pk) for pk in sample
                )
                diff_parts.append(
                    f"{len(missing_in_target)} rows in source missing from target"
                    f"{' (showing first 100)' if len(missing_in_target) > SAMPLE_SIZE else ''}."
                )
                diff_parts.append(f"Missing IDs in target: {ids}")

            if extra_in_target:
                sample = sorted(extra_in_target)[:SAMPLE_SIZE]
                ids = ", ".join(
                    str(pk[0]) if len(pk) == 1 else str(pk) for pk in sample
                )
                diff_parts.append(
                    f"{len(extra_in_target)} rows in target not in source"
                    f"{' (showing first 100)' if len(extra_in_target) > SAMPLE_SIZE else ''}."
                )
                diff_parts.append(f"Extra IDs in target: {ids}")

            if len(src_keys) >= MAX_ROWS or len(tgt_keys) >= MAX_ROWS:
                diff_parts.append(
                    f"(Comparison capped at {MAX_ROWS:,} rows per side — full table scan may show more)"
                )

            return TestResult(
                test_case=test_case,
                status=TestStatus.FAIL,
                source_value=len(src_keys),
                target_value=len(tgt_keys),
                diff="\n".join(diff_parts),
                duration_seconds=time.monotonic() - start,
            )
        except Exception as exc:
            logger.exception("Error in missing-rows check %s", test_case.id)
            return TestResult(
                test_case=test_case,
                status=TestStatus.ERROR,
                error_message=str(exc),
                duration_seconds=time.monotonic() - start,
            )
