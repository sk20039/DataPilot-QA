"""Connector Protocol definition."""
from __future__ import annotations

from typing import Any, Iterator, Protocol, runtime_checkable

from datamigrate_qa.models import TableMetadata


@runtime_checkable
class Connector(Protocol):
    """Protocol that all database connectors must implement."""

    def connect(self) -> None: ...

    def disconnect(self) -> None: ...

    def __enter__(self) -> "Connector": ...

    def __exit__(self, *args: Any) -> None: ...

    def list_tables(self, schema: str) -> list[str]: ...

    def get_table_metadata(self, schema: str, table: str) -> TableMetadata: ...

    def execute_scalar(self, sql: str) -> Any: ...

    def execute_query(self, sql: str, chunk_size: int = 10_000) -> Iterator[list[dict[str, Any]]]: ...

    @property
    def dialect_name(self) -> str: ...
