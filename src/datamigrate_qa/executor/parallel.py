"""Parallel test executor using ThreadPoolExecutor."""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable

from datamigrate_qa.connectors.base import Connector
from datamigrate_qa.connectors.registry import get_connector
from datamigrate_qa.config.models import AppConfig
from datamigrate_qa.models import TestCase, TestResult

from .runner import SequentialRunner

logger = logging.getLogger(__name__)


class ParallelRunner:
    """Runs test cases in parallel; each worker gets its own DB connections."""

    def __init__(
        self,
        app_config: AppConfig,
        max_workers: int = 4,
        progress_callback: Callable[[TestResult], None] | None = None,
    ) -> None:
        self._app_config = app_config
        self._max_workers = max_workers
        self._progress_callback = progress_callback

    def run(self, test_cases: list[TestCase]) -> list[TestResult]:
        """Execute test cases in parallel thread workers."""
        results: list[TestResult] = [None] * len(test_cases)  # type: ignore[list-item]

        def run_chunk(indexed_cases: list[tuple[int, TestCase]]) -> list[tuple[int, TestResult]]:
            src = get_connector(self._app_config.source)
            tgt = get_connector(self._app_config.target)
            with src, tgt:  # type: ignore[attr-defined]
                runner = SequentialRunner(src, tgt, self._progress_callback)
                return [
                    (idx, runner._run_one(case))
                    for idx, case in indexed_cases
                ]

        # Chunk test cases across workers
        chunks: list[list[tuple[int, TestCase]]] = [[] for _ in range(self._max_workers)]
        for idx, tc in enumerate(test_cases):
            chunks[idx % self._max_workers].append((idx, tc))

        with ThreadPoolExecutor(max_workers=self._max_workers) as executor:
            futures = [executor.submit(run_chunk, chunk) for chunk in chunks if chunk]
            for future in as_completed(futures):
                for idx, result in future.result():
                    results[idx] = result

        return results
