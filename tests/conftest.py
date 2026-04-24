"""Shared test fixtures."""
from __future__ import annotations

import pytest


@pytest.fixture
def sample_table_config():
    from datamigrate_qa.config.models import TableConfig
    return [
        TableConfig(source="public.orders", target="public.orders"),
        TableConfig(source="public.customers", target="public.customers"),
    ]
