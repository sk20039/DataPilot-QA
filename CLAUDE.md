# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**datamigrate-qa** is a Python tool that validates data integrity between source and target databases during migrations. It supports PostgreSQL, Snowflake, and Oracle via a protocol-based connector system. It has both a CLI (`datamigrate-qa run`) and a web UI (`ui/`).

## Web UI (FastAPI + React)

The UI lives in `ui/`. It wraps the core engine in a FastAPI backend and exposes a React frontend for QA users.

```
ui/
  backend/main.py        # FastAPI app — /api/connections/test, /api/runs
  backend/requirements.txt
  frontend/              # React + Vite + Tailwind + TypeScript
    src/
      App.tsx            # Main state + layout
      api.ts             # fetch wrappers
      types.ts           # shared TypeScript types
      components/
        ConnectionForm.tsx     # dialect-aware connection form with test button
        TableManager.tsx       # add/remove source→target table pairs
        GeneratorToggles.tsx   # enable/disable each check type
        ResultsDashboard.tsx   # summary cards + filterable results table
  start.ps1              # launches both servers and opens browser (Windows)
```

### Running the UI

```bash
# 1. Install backend extras (once)
pip install -e .
pip install -r ui/backend/requirements.txt

# 2. Install frontend deps (once)
cd ui/frontend && npm install

# 3a. Start everything (Windows PowerShell)
.\ui\start.ps1

# 3b. Or start manually in two terminals:
#   Terminal 1 — backend (from repo root):
uvicorn ui.backend.main:app --reload --port 8000
#   Terminal 2 — frontend:
cd ui/frontend && npm run dev

# Open http://localhost:5173
```

The Vite dev server proxies `/api/*` to `http://localhost:8000`. In production, build the frontend with `npm run build` and serve `dist/` from FastAPI using `StaticFiles`.

### UI architecture notes

- Backend stores run state in-memory (`_runs` dict + lock); runs execute in daemon threads.
- `testConnection` endpoint also returns available table names (used to populate dropdowns).
- `schema_check` in the API maps to `SchemaValidatorGenerator` (named differently to avoid Python keyword conflicts).
- Field Match is disabled by default in the UI (can be slow for large tables).
- `max_workers > 1` uses `ParallelRunner(AppConfig(...), max_workers=N)`; `max_workers == 1` uses `SequentialRunner`. `ParallelRunner` creates fresh per-worker DB connections internally.

## Commands

```bash
# Install for development
pip install -e ".[dev]"

# Run the tool
datamigrate-qa run --config examples/pg_to_pg.yaml
datamigrate-qa run --config config.yaml --workers 4 --verbose

# Testing
pytest tests/                         # all tests
pytest tests/unit/                    # unit tests only
pytest tests/integration/             # integration tests (requires Docker)
pytest tests/ -v --cov=src/           # with coverage
pytest tests/unit/test_models.py      # single test file

# Code quality
ruff check src/                       # lint
ruff format src/                      # format
mypy src/                             # type check (strict mode)
```

## Architecture

The pipeline flows: **Config → Connectors → Introspection → Mapping → Generators → Executor → Reporters**

### Key Layers

**Config** (`src/datamigrate_qa/config/`): Pydantic v2 models loaded from YAML. Supports `${ENV_VAR}` substitution and secret file references. `AppConfig` is the root model containing source/target `ConnectionConfig`, table list, and generator options.

**Connectors** (`src/datamigrate_qa/connectors/`): All connectors implement the `Connector` Protocol in `base.py`. The `ConnectorRegistry` in `registry.py` maps dialect strings to implementations. Snowflake and Oracle are optional imports — they raise `ImportError` with install hints if the extras aren't installed.

**Mapping** (`src/datamigrate_qa/mapping/`): Auto-mapper does two-pass matching (exact → case-insensitive). YAML mapper allows manual column overrides. Unmatched columns generate warnings, not errors.

**Generators** (`src/datamigrate_qa/generators/`): Each implements the `TestGenerator` Protocol and produces `TestCase` objects. The 5 generators are: `row_count`, `schema_validator`, `field_match`, `null_duplicate`, `aggregate_recon`. Each is independently enabled/disabled in config.

**Executor** (`src/datamigrate_qa/executor/`): `SequentialRunner` is the default; `ParallelRunner` uses `ThreadPoolExecutor` with per-worker DB connections (connections are not thread-safe). Comparison strategies: `EXACT`, `NUMERIC_TOLERANCE`, `SET_EQUALITY`, `HASH_MATCH`.

**Reporting** (`src/datamigrate_qa/reporting/`): Three reporters — Rich console tables, JSON file, HTML file (via Jinja2). All receive a `RunReport` dataclass.

### Core Models (`src/datamigrate_qa/models.py`)

- `TestCase`: query pair + comparison strategy + tolerance
- `TestResult`: status (PASS/FAIL/ERROR/SKIPPED) + actual values + diff
- `RunReport`: aggregated results with pass/fail/error/skipped counts
- `CanonicalType`: normalized type enum used across dialects

### Design Conventions

- Protocol-based extensibility: new connectors/generators implement the relevant Protocol
- `from __future__ import annotations` used throughout; Python 3.11+ required
- Dataclasses for runtime models, Pydantic v2 for config validation
- `execute_query()` returns an iterator for chunked large result sets
- CLI uses lazy imports inside the `run()` command function for fast startup
- Ruff line-length is 100; mypy strict mode is enforced
