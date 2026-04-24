"""Test executors."""
from .parallel import ParallelRunner
from .runner import SequentialRunner

__all__ = ["ParallelRunner", "SequentialRunner"]
