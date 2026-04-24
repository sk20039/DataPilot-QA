import type {
  ConnectionConfig,
  ConnectionTestResult,
  GeneratorsConfig,
  RunReport,
  RunStatusResponse,
  TableEntry,
  AnalyzeRunResponse,
  FailureAnalysis,
  GeneratedTestCase,
} from './types'

interface RunRequest {
  source: ConnectionConfig
  target: ConnectionConfig
  tables: { source: string; target: string; primaryKey?: string }[]
  generators: GeneratorsConfig
  max_workers: number
  custom_tests: {
    description: string
    source_sql: string
    target_sql: string
    comparison_strategy: 'EXACT' | 'NUMERIC_TOLERANCE'
    tolerance: number
  }[]
}

export async function testConnection(conn: ConnectionConfig): Promise<ConnectionTestResult> {
  const res = await fetch('/api/connections/test', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(conn),
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export async function startRun(payload: RunRequest): Promise<{ run_id: string }> {
  const res = await fetch('/api/runs', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export async function getRun(runId: string): Promise<RunStatusResponse> {
  const res = await fetch(`/api/runs/${runId}`)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export function exportResultsJson(report: RunReport): void {
  const blob = new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `qa-report-${report.run_id.slice(0, 8)}.json`
  a.click()
  URL.revokeObjectURL(url)
}

// ── AI API functions ──────────────────────────────────────────────────────────

export async function analyzeRun(runId: string): Promise<AnalyzeRunResponse> {
  const res = await fetch(`/api/ai/analyze-run/${runId}`, { method: 'POST' })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }))
    throw new Error(err.detail ?? `HTTP ${res.status}`)
  }
  return res.json()
}

export async function explainResult(runId: string, testId: string): Promise<FailureAnalysis> {
  const res = await fetch('/api/ai/explain-result', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ run_id: runId, test_id: testId }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }))
    throw new Error(err.detail ?? `HTTP ${res.status}`)
  }
  return res.json()
}

export async function generateTest(params: {
  source_conn: ConnectionConfig
  target_conn: ConnectionConfig
  table_pair?: TableEntry
  prompt: string
}): Promise<GeneratedTestCase> {
  const res = await fetch('/api/ai/generate-test', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }))
    throw new Error(err.detail ?? `HTTP ${res.status}`)
  }
  return res.json()
}
