# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**datamigrate-qa** is a Python tool that validates data integrity between source and target databases during migrations. It supports PostgreSQL, Snowflake, and Oracle via a protocol-based connector system. It has both a CLI (`datamigrate-qa run`) and a web UI (`ui/`).

## Web UI (FastAPI + React)

The UI lives in `ui/`. It wraps the core engine in a FastAPI backend and exposes a React frontend for QA users.

```
ui/
  backend/main.py        # FastAPI app — /api/connections/test, /api/runs, /api/ai/*
  backend/requirements.txt
  frontend/              # React + Vite + Tailwind + TypeScript
    src/
      App.tsx            # Main state + layout
      api.ts             # fetch wrappers (including AI endpoints)
      types.ts           # shared TypeScript types (including AI response types)
      components/
        ConnectionForm.tsx     # dialect-aware connection form with test button
        TableManager.tsx       # add/remove source→target table pairs
        GeneratorToggles.tsx   # enable/disable each check type
        ResultsDashboard.tsx   # summary cards + filterable results table + AI buttons
        CustomTestEditor.tsx   # custom SQL test cases + AI generator
        AISummaryPanel.tsx     # run-level AI health report card
        AITestGenerator.tsx    # natural language → SQL input panel
  start.ps1              # launches both servers and opens browser (Windows)
```

### Running the UI

```bash
# 1. Install backend extras (once)
pip install -e ".[ai]"
pip install -r ui/backend/requirements.txt

# 2. Install frontend deps (once)
cd ui/frontend && npm install

# 3a. Start everything (Windows PowerShell)
.\ui\start.ps1

# 3b. Or start manually in two terminals:
#   Terminal 1 — backend (from repo root):
#   Set API key first if using AI features:
#   $env:ANTHROPIC_API_KEY = "sk-ant-..."
python -m uvicorn ui.backend.main:app --reload --port 8000
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
- AI endpoints (`/api/ai/*`) return HTTP 503 if `ANTHROPIC_API_KEY` is not set or `anthropic` package is not installed — they never crash the server.
- Run state stores `source_dialect` and `target_dialect` so AI analysis has migration context.

## Commands

```bash
# Install for development
pip install -e ".[dev]"

# Install AI features (requires ANTHROPIC_API_KEY env var)
pip install -e ".[ai]"

# Run the tool
datamigrate-qa run --config examples/pg_to_pg.yaml
datamigrate-qa run --config config.yaml --workers 4 --verbose
datamigrate-qa run --config config.yaml --ai          # with AI summary + failure analysis

# Analyze an existing JSON report with AI
datamigrate-qa analyze --report report.json

# Generate a custom test case from natural language
datamigrate-qa generate-test --config config.yaml \
  --prompt "ensure revenue totals match within 1%" \
  --table orders

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

**Connectors** (`src/datamigrate_qa/connectors/`): All connectors implement the `Connector` Protocol in `base.py`. The `ConnectorRegistry` in `registry.py` maps dialect strings to implementations. MySQL (`mysql`/`mariadb`), Snowflake, and Oracle are optional imports — they raise `ImportError` with install hints if the extras aren't installed. In MySQL, schema = database name; the connector uses `DictCursor` throughout and strips type display widths (e.g. `int(11)` → `int`) before mapping to `CanonicalType`.

**Mapping** (`src/datamigrate_qa/mapping/`): Auto-mapper does two-pass matching (exact → case-insensitive). YAML mapper allows manual column overrides. Unmatched columns generate warnings, not errors.

**Generators** (`src/datamigrate_qa/generators/`): Each implements the `TestGenerator` Protocol and produces `TestCase` objects. The 6 generators are: `row_count`, `schema_validator`, `field_match`, `null_duplicate`, `aggregate_recon`, `missing_rows`. Each is independently enabled/disabled in config. Note: `missing_rows` fetches PKs from both sides, diffs in Python, and reports exact missing/extra IDs (capped at 10,000 rows per side). It only runs on tables with a detected or overridden PK, and is disabled by default. **It is not yet in `GeneratorsConfig` (`config/models.py`), so it cannot be enabled via YAML/CLI — only via the UI (`GeneratorsRequest` in `ui/backend/main.py`).**

**Executor** (`src/datamigrate_qa/executor/`): `SequentialRunner` is the default; `ParallelRunner` uses `ThreadPoolExecutor` with per-worker DB connections (connections are not thread-safe). Comparison strategies: `EXACT`, `NUMERIC_TOLERANCE`, `SET_EQUALITY`, `HASH_MATCH`.

**Reporting** (`src/datamigrate_qa/reporting/`): Three reporters — Rich console tables, JSON file, HTML file (via Jinja2). All receive a `RunReport` dataclass. `print_ai_section()` appends AI analysis to the console output when `--ai` is active.

**AI** (`src/datamigrate_qa/ai/`): Optional module — requires `pip install -e ".[ai]"` and `ANTHROPIC_API_KEY`.
- `client.py`: soft import of `anthropic`; `get_client()` / `is_available()`.
- `analyst.py`: batch failure analysis via `claude-haiku-4-5`; single API call for all FAIL/ERROR results. Also exposes `analyze_one()` for single-result explanation, used by the `/api/ai/explain-result` endpoint.
- `summarizer.py`: executive run summary + risk score via `claude-haiku-4-5`.
- `nl_generator.py`: natural language → SQL via `claude-sonnet-4-6`; detects numeric/date/PK/FK columns from `SchemaContext` to write smarter SQL; validates generated SQL is read-only before returning.

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
- AI module uses soft imports — missing `anthropic` package degrades gracefully with a clear message, never crashes the core tool
- AI prompts instruct Claude to respond with raw JSON only; markdown fences are stripped before `json.loads()` as a safety net
