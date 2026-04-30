# datamigrate-qa

Automated data validation tool for database migrations. Validates data integrity between source and target databases across PostgreSQL, Snowflake, MySql and Oracle — with a web UI and optional AI-powered analysis.

![Python](https://img.shields.io/badge/python-3.11+-blue) ![License](https://img.shields.io/badge/license-MIT-green)

---

## What it does

When migrating data between databases, datamigrate-qa runs a battery of checks to confirm nothing was lost, corrupted, or changed:

| Check | What it validates |
|---|---|
| **Row Count** | Source and target have the same number of rows |
| **Schema** | Column names and types are consistent |
| **Null / Duplicate** | No unexpected nulls introduced; no duplicate primary keys |
| **Field Match** | Sampled field values match between source and target |
| **Aggregate Recon** | SUM, AVG, MIN, MAX of numeric columns reconcile |
| **Missing Rows** | Which specific primary key values are in source but not target (and vice versa) |

Results are reported as PASS / FAIL / ERROR / SKIPPED with diffs for every failure.

---

## AI features (optional)

Requires `ANTHROPIC_API_KEY` and `pip install -e ".[ai]"`.

- **AI Run Summary** — after a run, Claude generates an executive health report with a risk score (0–100) and a Go / No-Go recommendation
- **AI Failure Analyst** — click "Explain with AI" on any failed row to get a plain-English root cause, severity label, and investigation checklist
- **Natural Language Test Generator** — describe a test in plain English ("ensure revenue totals match within 1%") and Claude writes the SQL for both source and target, auto-detecting numeric/date/PK/FK columns to produce smarter queries

---

## Quick start

### Prerequisites

- Python 3.11+
- Node.js 18+ (for the web UI)
- A source and target database (PostgreSQL, Snowflake, MySQL/MariaDB, or Oracle)

### Install

```bash
git clone https://github.com/sk20039/datamigrate-qa.git
cd datamigrate-qa

# Core tool
pip install -e .

# AI features (optional)
pip install -e ".[ai]"

# Frontend dependencies
cd ui/frontend && npm install && cd ../..
```

### Run via CLI

```bash
# Copy and edit the example config
cp examples/pg_to_pg.yaml config.yaml

datamigrate-qa run --config config.yaml
datamigrate-qa run --config config.yaml --ai        # with AI summary
datamigrate-qa run --config config.yaml --workers 4 --verbose
```

### Run via Web UI

```powershell
# Windows PowerShell — starts backend + frontend and opens browser
$env:ANTHROPIC_API_KEY = "sk-ant-..."   # optional, for AI features
.\ui\start.ps1
```

Or manually in two terminals:

```bash
# Terminal 1 — backend
python -m uvicorn ui.backend.main:app --reload --port 8000

# Terminal 2 — frontend
cd ui/frontend && npm run dev
```

Open **http://localhost:5173**

---

## Configuration

```yaml
# config.yaml
source:
  dialect: postgresql
  host: localhost
  port: 5432
  database: source_db
  username: user
  password: secret

target:
  dialect: postgresql
  host: localhost
  port: 5433
  database: target_db
  username: user
  password: secret

tables:
  - source: public.orders
    target: public.orders
  - source: public.customers
    target: public.customers
    primary_key_override: [id]   # optional — override auto-detected PK

generators:
  row_count:    { enabled: true }
  schema:       { enabled: true }
  null_duplicate: { enabled: true }
  aggregate_recon: { enabled: true, tolerance: 1e-6 }
  field_match:  { enabled: false }   # slow on large tables
  missing_rows: { enabled: false }   # identifies specific missing PKs; requires a PK

max_workers: 4   # parallel workers (1 = sequential)

output:
  json: report.json
  html: report.html
```

Supports `${ENV_VAR}` substitution and file-based secrets anywhere in the config.

---

## CLI reference

```bash
# Run validation
datamigrate-qa run --config config.yaml [--workers N] [--verbose] [--ai]

# Analyze a saved JSON report with AI
datamigrate-qa analyze --report report.json

# Generate a custom test case from natural language
datamigrate-qa generate-test --config config.yaml \
  --prompt "ensure revenue totals match within 1%" \
  --table orders
```

---

## Supported databases

| Database | Dialect string | Extra |
|---|---|---|
| PostgreSQL | `postgresql` | included |
| MySQL / MariaDB | `mysql` / `mariadb` | `pip install -e ".[mysql]"` |
| Snowflake | `snowflake` | `pip install -e ".[snowflake]"` |
| Oracle | `oracle` | `pip install -e ".[oracle]"` |

---

## Project structure

```
src/datamigrate_qa/
  ai/               # Claude-powered analysis (optional)
  config/           # Pydantic config models + YAML loader
  connectors/       # DB connectors (Protocol-based)
  introspection/    # Schema inspector
  mapping/          # Auto-mapper + YAML overrides
  generators/       # 6 test case generators
  executor/         # Sequential + parallel runners
  reporting/        # Console (Rich), JSON, HTML reporters
  cli.py            # Typer CLI entry point
  models.py         # Core dataclasses (TestCase, TestResult, RunReport)

ui/
  backend/main.py   # FastAPI app
  frontend/src/     # React + Vite + Tailwind + TypeScript

tests/
  unit/             # Pure unit tests (no DB required)
  integration/      # End-to-end tests (requires Docker)
```

---

## Development

```bash
pip install -e ".[dev]"

pytest tests/unit/                    # fast tests, no DB
pytest tests/integration/            # requires Docker (docker-compose up)
pytest tests/ -v --cov=src/

ruff check src/
ruff format src/
mypy src/
```

---

## License

MIT
