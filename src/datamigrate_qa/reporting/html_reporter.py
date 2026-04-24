"""HTML reporter using Jinja2."""
from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, BaseLoader

from datamigrate_qa.models import RunReport, TestStatus

_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Migration QA Report</title>
<style>
  body { font-family: sans-serif; margin: 2rem; background: #f8f9fa; }
  h1 { color: #333; }
  .summary { display: flex; gap: 1rem; margin: 1rem 0; }
  .badge { padding: .4rem .8rem; border-radius: 4px; font-weight: bold; }
  .pass { background: #d4edda; color: #155724; }
  .fail { background: #f8d7da; color: #721c24; }
  .error { background: #fff3cd; color: #856404; }
  .skipped { background: #e2e3e5; color: #383d41; }
  table { width: 100%; border-collapse: collapse; background: #fff; }
  th { background: #343a40; color: #fff; padding: .5rem; text-align: left; }
  td { padding: .5rem; border-bottom: 1px solid #dee2e6; font-size: .9rem; }
  tr:hover { background: #f1f3f5; }
  .status-PASS { color: #155724; font-weight: bold; }
  .status-FAIL { color: #721c24; font-weight: bold; }
  .status-ERROR { color: #856404; font-weight: bold; }
  .status-SKIPPED { color: #6c757d; }
  .meta { color: #666; font-size: .85rem; margin-bottom: 1rem; }
</style>
</head>
<body>
<h1>Migration QA Report</h1>
<p class="meta">Run ID: {{ report.run_id }} | Started: {{ report.started_at }}</p>
<div class="summary">
  <span class="badge pass">{{ report.passed }} PASS</span>
  <span class="badge fail">{{ report.failed }} FAIL</span>
  <span class="badge error">{{ report.errors }} ERROR</span>
  <span class="badge skipped">{{ report.skipped }} SKIPPED</span>
</div>
<table>
  <thead>
    <tr>
      <th>Category</th>
      <th>Description</th>
      <th>Status</th>
      <th>Source</th>
      <th>Target</th>
      <th>Diff / Error</th>
      <th>Duration (s)</th>
    </tr>
  </thead>
  <tbody>
  {% for result in report.results %}
    <tr>
      <td>{{ result.test_case.category }}</td>
      <td>{{ result.test_case.description }}</td>
      <td class="status-{{ result.status.value }}">{{ result.status.value }}</td>
      <td>{{ result.source_value if result.source_value is not none else '—' }}</td>
      <td>{{ result.target_value if result.target_value is not none else '—' }}</td>
      <td>{{ (result.diff or result.error_message or '')[:120] }}</td>
      <td>{{ '%.3f' % result.duration_seconds }}</td>
    </tr>
  {% endfor %}
  </tbody>
</table>
</body>
</html>
"""


def write_html_report(report: RunReport, path: str | Path) -> None:
    """Write the run report as HTML."""
    env = Environment(loader=BaseLoader())
    template = env.from_string(_TEMPLATE)
    html = template.render(report=report)
    Path(path).write_text(html, encoding="utf-8")
