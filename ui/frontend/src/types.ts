export interface ConnectionConfig {
  dialect: string
  host: string
  port: number
  database: string
  username: string
  password: string
  schema_name: string
  account: string
}

export interface TableEntry {
  source: string
  target: string
  primaryKey?: string
}

export interface GeneratorSetting {
  enabled: boolean
  tolerance: number
}

export interface GeneratorsConfig {
  row_count: GeneratorSetting
  schema_check: GeneratorSetting
  field_match: GeneratorSetting
  null_duplicate: GeneratorSetting
  aggregate_recon: GeneratorSetting
}

export interface TestResultItem {
  id: string
  category: string
  description: string
  source_table: string
  target_table: string
  status: 'PASS' | 'FAIL' | 'ERROR' | 'SKIPPED'
  source_value: string | null
  target_value: string | null
  diff: string
  duration_seconds: number
  error_message: string
}

export interface RunReport {
  run_id: string
  total: number
  passed: number
  failed: number
  errors: number
  skipped: number
  all_passed: boolean
  warnings: string[]
  results: TestResultItem[]
}

export interface RunStatusResponse {
  run_id: string
  status: 'running' | 'completed' | 'error'
  progress: string
  report: RunReport | null
  error: string | null
}

export interface ConnectionTestResult {
  ok: boolean
  tables?: string[]
  error?: string
}

export interface CustomTestEntry {
  id: string
  description: string
  source_sql: string
  target_sql: string
  comparison_strategy: 'EXACT' | 'NUMERIC_TOLERANCE'
  tolerance: number
}

// ── AI types ──────────────────────────────────────────────────────────────────

export interface RunSummary {
  overall_status: 'PASS' | 'FAIL' | 'CAUTION'
  risk_score: number
  headline: string
  key_findings: string[]
  patterns: string[]
  recommendation: 'Go' | 'No-Go' | 'Investigate further'
  details: string
}

export interface FailureAnalysis {
  likely_cause: string
  explanation: string
  investigate: string[]
  severity: 'critical' | 'warning' | 'informational'
}

export interface AnalyzeRunResponse {
  summary: RunSummary
  analyses: Record<string, FailureAnalysis>
}

export interface GeneratedTestCase {
  source_sql: string
  target_sql: string
  comparison_strategy: 'EXACT' | 'NUMERIC_TOLERANCE'
  tolerance: number
  description: string
  explanation: string
}
