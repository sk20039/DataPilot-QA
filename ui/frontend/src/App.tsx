import { useState, useRef } from 'react'
import ConnectionForm from './components/ConnectionForm'
import TableManager from './components/TableManager'
import GeneratorToggles from './components/GeneratorToggles'
import CustomTestEditor from './components/CustomTestEditor'
import ResultsDashboard from './components/ResultsDashboard'
import { testConnection, startRun, getRun } from './api'
import type {
  ConnectionConfig,
  TableEntry,
  GeneratorsConfig,
  RunReport,
  ConnectionTestResult,
  CustomTestEntry,
} from './types'

const defaultConn = (overrides?: Partial<ConnectionConfig>): ConnectionConfig => ({
  dialect: 'postgresql',
  host: 'localhost',
  port: 5432,
  database: '',
  username: '',
  password: '',
  schema_name: '',
  account: '',
  ...overrides,
})

const defaultGenerators = (): GeneratorsConfig => ({
  row_count: { enabled: true, tolerance: 1e-6 },
  schema_check: { enabled: true, tolerance: 1e-6 },
  field_match: { enabled: false, tolerance: 1e-6 },
  null_duplicate: { enabled: true, tolerance: 1e-6 },
  aggregate_recon: { enabled: true, tolerance: 1e-6 },
})

type RunPhase = 'idle' | 'running' | 'completed' | 'error'

export default function App() {
  // Config state
  const [source, setSource] = useState<ConnectionConfig>(defaultConn())
  const [target, setTarget] = useState<ConnectionConfig>(defaultConn({ port: 5433 }))
  const [tables, setTables] = useState<TableEntry[]>([])
  const [generators, setGenerators] = useState<GeneratorsConfig>(defaultGenerators())
  const [customTests, setCustomTests] = useState<CustomTestEntry[]>([])
  const [maxWorkers, setMaxWorkers] = useState(4)

  // Test connection state
  const [srcTest, setSrcTest] = useState<ConnectionTestResult | null>(null)
  const [tgtTest, setTgtTest] = useState<ConnectionTestResult | null>(null)
  const [srcTesting, setSrcTesting] = useState(false)
  const [tgtTesting, setTgtTesting] = useState(false)

  // Run state
  const [phase, setPhase] = useState<RunPhase>('idle')
  const [progress, setProgress] = useState('')
  const [report, setReport] = useState<RunReport | null>(null)
  const [runError, setRunError] = useState<string | null>(null)
  const pollingRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const sourceTables = srcTest?.ok ? (srcTest.tables ?? []) : []
  const targetTables = tgtTest?.ok ? (tgtTest.tables ?? []) : []

  const handleTestSource = async () => {
    setSrcTesting(true)
    setSrcTest(null)
    try {
      const result = await testConnection(source)
      setSrcTest(result)
    } catch {
      setSrcTest({ ok: false, error: 'Network error — is the backend running?' })
    } finally {
      setSrcTesting(false)
    }
  }

  const handleTestTarget = async () => {
    setTgtTesting(true)
    setTgtTest(null)
    try {
      const result = await testConnection(target)
      setTgtTest(result)
    } catch {
      setTgtTest({ ok: false, error: 'Network error — is the backend running?' })
    } finally {
      setTgtTesting(false)
    }
  }

  const pollRun = (runId: string) => {
    pollingRef.current = setTimeout(async () => {
      try {
        const status = await getRun(runId)
        setProgress(status.progress)
        if (status.status === 'running') {
          pollRun(runId)
        } else if (status.status === 'completed' && status.report) {
          setPhase('completed')
          setReport(status.report)
        } else if (status.status === 'error') {
          setPhase('error')
          setRunError(status.error ?? 'Unknown error')
        }
      } catch {
        // Retry on network hiccup
        pollRun(runId)
      }
    }, 1500)
  }

  const handleRun = async () => {
    setPhase('running')
    setProgress('Starting…')
    setReport(null)
    setRunError(null)

    try {
      const { run_id } = await startRun({
        source,
        target,
        tables,
        generators,
        max_workers: maxWorkers,
        custom_tests: customTests.map(({ id: _id, ...rest }) => rest),
      })
      pollRun(run_id)
    } catch {
      setPhase('error')
      setRunError('Failed to start run — is the backend running?')
    }
  }

  const handleReset = () => {
    if (pollingRef.current) clearTimeout(pollingRef.current)
    setPhase('idle')
    setReport(null)
    setRunError(null)
    setProgress('')
  }

  const canRun = (tables.length > 0 || customTests.length > 0) && phase !== 'running'

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-slate-800 text-white px-6 py-4">
        <div className="max-w-6xl mx-auto flex items-center justify-between">
          <div>
            <h1 className="text-lg font-semibold tracking-tight">DataMigrate QA</h1>
            <p className="text-slate-400 text-xs mt-0.5">Automated data validation between source and target databases</p>
          </div>
          {phase !== 'idle' && (
            <button
              onClick={handleReset}
              className="text-slate-300 hover:text-white text-sm underline underline-offset-2"
            >
              Start over
            </button>
          )}
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-4 py-8 space-y-6">
        {/* Connections */}
        <section>
          <p className="text-xs font-semibold uppercase tracking-widest text-gray-400 mb-3">
            1 — Connections
          </p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <ConnectionForm
              label="Source Database"
              value={source}
              onChange={setSource}
              onTest={handleTestSource}
              testing={srcTesting}
              testResult={srcTest}
            />
            <ConnectionForm
              label="Target Database"
              value={target}
              onChange={setTarget}
              onTest={handleTestTarget}
              testing={tgtTesting}
              testResult={tgtTest}
            />
          </div>
        </section>

        {/* Tables */}
        <section>
          <p className="text-xs font-semibold uppercase tracking-widest text-gray-400 mb-3">
            2 — Tables
          </p>
          <TableManager
            tables={tables}
            onChange={setTables}
            sourceTables={sourceTables}
            targetTables={targetTables}
          />
        </section>

        {/* Generators */}
        <section>
          <p className="text-xs font-semibold uppercase tracking-widest text-gray-400 mb-3">
            3 — Validation Checks
          </p>
          <GeneratorToggles value={generators} onChange={setGenerators} />
        </section>

        {/* Custom test cases */}
        <section>
          <p className="text-xs font-semibold uppercase tracking-widest text-gray-400 mb-3">
            4 — Custom Test Cases
          </p>
          <CustomTestEditor
            tests={customTests}
            onChange={setCustomTests}
            sourceConn={source}
            targetConn={target}
            tablePairs={tables}
          />
        </section>

        {/* Run controls */}
        <section className="bg-white rounded-xl border border-gray-200 px-5 py-4">
          <div className="flex items-center gap-6 flex-wrap">
            <div className="flex items-center gap-3">
              <label className="text-sm font-medium text-gray-700">Parallel workers</label>
              <input
                type="number"
                min={1}
                max={16}
                value={maxWorkers}
                onChange={(e) => setMaxWorkers(Number(e.target.value))}
                className="w-16 border border-gray-300 rounded px-2 py-1 text-sm text-center focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <button
              onClick={handleRun}
              disabled={!canRun}
              className="px-6 py-2 bg-blue-600 text-white font-semibold rounded-lg hover:bg-blue-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors text-sm"
            >
              {phase === 'running' ? 'Running…' : 'Run Validation'}
            </button>

            {phase === 'running' && (
              <div className="flex items-center gap-3 text-sm text-gray-600">
                {/* Spinner */}
                <svg className="animate-spin h-4 w-4 text-blue-600" viewBox="0 0 24 24" fill="none">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path
                    className="opacity-75"
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"
                  />
                </svg>
                <span>{progress}</span>
              </div>
            )}
          </div>
        </section>

        {/* Error state */}
        {phase === 'error' && runError && (
          <div className="bg-red-50 border border-red-300 rounded-xl px-5 py-4 text-red-800 text-sm">
            <strong>Run failed:</strong> {runError}
          </div>
        )}

        {/* Results */}
        {phase === 'completed' && report && (
          <section>
            <p className="text-xs font-semibold uppercase tracking-widest text-gray-400 mb-3">
              Results
            </p>
            <ResultsDashboard report={report} />
          </section>
        )}
      </main>
    </div>
  )
}
