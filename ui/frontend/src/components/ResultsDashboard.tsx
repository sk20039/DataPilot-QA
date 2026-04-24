import { useState } from 'react'
import type { RunReport, TestResultItem, AnalyzeRunResponse, FailureAnalysis } from '../types'
import { exportResultsJson, analyzeRun, explainResult } from '../api'
import AISummaryPanel from './AISummaryPanel'

const STATUS_STYLES: Record<TestResultItem['status'], string> = {
  PASS: 'bg-green-100 text-green-800',
  FAIL: 'bg-red-100 text-red-800',
  ERROR: 'bg-orange-100 text-orange-800',
  SKIPPED: 'bg-gray-100 text-gray-600',
}

const SEVERITY_STYLES: Record<NonNullable<FailureAnalysis['severity']>, string> = {
  critical: 'bg-red-50 border-red-300 text-red-800',
  warning: 'bg-yellow-50 border-yellow-300 text-yellow-800',
  informational: 'bg-blue-50 border-blue-300 text-blue-800',
}

type Filter = 'ALL' | TestResultItem['status']

function StatCard({ label, count, color }: { label: string; count: number; color: string }) {
  return (
    <div className={`rounded-lg border p-4 text-center ${color}`}>
      <p className="text-3xl font-bold">{count}</p>
      <p className="text-sm font-medium mt-1">{label}</p>
    </div>
  )
}

function Spinner() {
  return (
    <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
    </svg>
  )
}

interface Props {
  report: RunReport
}

export default function ResultsDashboard({ report }: Props) {
  const [filter, setFilter] = useState<Filter>('ALL')
  const [expandedId, setExpandedId] = useState<string | null>(null)

  // AI state
  const [aiLoading, setAiLoading] = useState(false)
  const [aiError, setAiError] = useState<string | null>(null)
  const [aiData, setAiData] = useState<AnalyzeRunResponse | null>(null)

  // Per-row explain state
  const [explaining, setExplaining] = useState<Record<string, boolean>>({})
  const [explanations, setExplanations] = useState<Record<string, FailureAnalysis>>({})
  const [explainErrors, setExplainErrors] = useState<Record<string, string>>({})

  const filtered =
    filter === 'ALL' ? report.results : report.results.filter((r) => r.status === filter)

  const ORDER: Record<TestResultItem['status'], number> = { FAIL: 0, ERROR: 1, PASS: 2, SKIPPED: 3 }
  const sorted = [...filtered].sort((a, b) => ORDER[a.status] - ORDER[b.status])

  const bannerClass = report.all_passed
    ? 'bg-green-50 border-green-300 text-green-800'
    : 'bg-red-50 border-red-300 text-red-800'

  const filterBtn = (f: Filter, label: string) => (
    <button
      onClick={() => setFilter(f)}
      className={`px-3 py-1 rounded-full text-sm font-medium transition-colors ${
        filter === f ? 'bg-gray-800 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
      }`}
    >
      {label}
    </button>
  )

  const handleAnalyzeRun = async () => {
    setAiLoading(true)
    setAiError(null)
    try {
      const data = await analyzeRun(report.run_id)
      setAiData(data)
    } catch (err) {
      setAiError(err instanceof Error ? err.message : 'AI analysis failed')
    } finally {
      setAiLoading(false)
    }
  }

  const handleExplain = async (resultId: string) => {
    setExplaining((prev) => ({ ...prev, [resultId]: true }))
    setExplainErrors((prev) => { const n = { ...prev }; delete n[resultId]; return n })
    try {
      const analysis = await explainResult(report.run_id, resultId)
      setExplanations((prev) => ({ ...prev, [resultId]: analysis }))
    } catch (err) {
      setExplainErrors((prev) => ({
        ...prev,
        [resultId]: err instanceof Error ? err.message : 'AI explain failed',
      }))
    } finally {
      setExplaining((prev) => { const n = { ...prev }; delete n[resultId]; return n })
    }
  }

  // Merge bulk AI analyses into per-row explanations
  const mergedExplanations = { ...explanations }
  if (aiData?.analyses) {
    for (const [tid, analysis] of Object.entries(aiData.analyses)) {
      if (!(tid in mergedExplanations)) {
        mergedExplanations[tid] = analysis
      }
    }
  }

  return (
    <div className="space-y-5">
      {/* Banner */}
      <div className={`rounded-xl border-2 px-5 py-4 flex items-center justify-between ${bannerClass}`}>
        <div>
          <p className="font-semibold text-lg">
            {report.all_passed ? '✓ All checks passed' : '✗ Some checks failed'}
          </p>
          <p className="text-sm opacity-80">Run ID: {report.run_id}</p>
        </div>
        <div className="flex items-center gap-3 flex-wrap">
          {/* AI Summary button */}
          {!aiData && (
            <button
              onClick={handleAnalyzeRun}
              disabled={aiLoading}
              className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium rounded-lg bg-purple-600 text-white hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {aiLoading ? <Spinner /> : <span>✦</span>}
              {aiLoading ? 'Analyzing…' : 'AI Summary'}
            </button>
          )}
          <button
            onClick={() => exportResultsJson(report)}
            className="px-4 py-2 text-sm font-medium rounded-lg bg-white border border-current opacity-80 hover:opacity-100 transition-opacity"
          >
            Export JSON
          </button>
        </div>
      </div>

      {/* AI error */}
      {aiError && (
        <div className="bg-red-50 border border-red-300 rounded-xl px-4 py-3 text-sm text-red-800">
          <strong>AI analysis failed:</strong> {aiError}
        </div>
      )}

      {/* AI Summary panel */}
      {aiData?.summary && <AISummaryPanel summary={aiData.summary} />}

      {/* Stat cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <StatCard label="Passed" count={report.passed} color="border-green-200 bg-green-50 text-green-700" />
        <StatCard label="Failed" count={report.failed} color="border-red-200 bg-red-50 text-red-700" />
        <StatCard label="Errors" count={report.errors} color="border-orange-200 bg-orange-50 text-orange-700" />
        <StatCard label="Skipped" count={report.skipped} color="border-gray-200 bg-gray-50 text-gray-600" />
      </div>

      {/* Warnings */}
      {report.warnings.length > 0 && (
        <div className="bg-yellow-50 border border-yellow-200 rounded-xl p-4">
          <p className="text-sm font-medium text-yellow-800 mb-2">Warnings</p>
          <ul className="space-y-1">
            {report.warnings.map((w, i) => (
              <li key={i} className="text-xs text-yellow-700">
                • {w}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Results table */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <div className="flex items-center gap-2 px-5 py-3 border-b border-gray-100 flex-wrap">
          <span className="text-sm text-gray-500 mr-1">Filter:</span>
          {filterBtn('ALL', `All (${report.total})`)}
          {filterBtn('PASS', `Pass (${report.passed})`)}
          {filterBtn('FAIL', `Fail (${report.failed})`)}
          {filterBtn('ERROR', `Error (${report.errors})`)}
          {filterBtn('SKIPPED', `Skipped (${report.skipped})`)}
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs font-medium text-gray-500 border-b border-gray-100">
                <th className="px-4 py-3 w-20">Status</th>
                <th className="px-4 py-3">Category</th>
                <th className="px-4 py-3">Description</th>
                <th className="px-4 py-3">Table</th>
                <th className="px-4 py-3 text-right">Duration</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {sorted.map((r) => (
                <>
                  <tr
                    key={r.id}
                    onClick={() => setExpandedId(expandedId === r.id ? null : r.id)}
                    className="hover:bg-gray-50 cursor-pointer"
                  >
                    <td className="px-4 py-3">
                      <span
                        className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${STATUS_STYLES[r.status]}`}
                      >
                        {r.status}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-gray-600 font-mono text-xs">{r.category}</td>
                    <td className="px-4 py-3 text-gray-800">{r.description}</td>
                    <td className="px-4 py-3 font-mono text-xs text-gray-500">{r.source_table}</td>
                    <td className="px-4 py-3 text-right text-gray-400 text-xs tabular-nums">
                      {r.duration_seconds}s
                    </td>
                  </tr>

                  {/* Expanded detail row */}
                  {expandedId === r.id && (
                    <tr key={`${r.id}-detail`} className="bg-gray-50">
                      <td colSpan={5} className="px-4 py-3">
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
                          <div>
                            <p className="font-medium text-gray-600 mb-1">Source value</p>
                            <pre className="font-mono bg-white border border-gray-200 rounded p-2 overflow-x-auto text-gray-800">
                              {r.source_value ?? '—'}
                            </pre>
                          </div>
                          <div>
                            <p className="font-medium text-gray-600 mb-1">Target value</p>
                            <pre className="font-mono bg-white border border-gray-200 rounded p-2 overflow-x-auto text-gray-800">
                              {r.target_value ?? '—'}
                            </pre>
                          </div>
                          {r.diff && (
                            <div className="sm:col-span-2">
                              <p className="font-medium text-gray-600 mb-1">Diff</p>
                              <pre className="font-mono bg-white border border-red-200 rounded p-2 overflow-x-auto text-red-700">
                                {r.diff}
                              </pre>
                            </div>
                          )}
                          {r.error_message && (
                            <div className="sm:col-span-2">
                              <p className="font-medium text-gray-600 mb-1">Error</p>
                              <pre className="font-mono bg-white border border-orange-200 rounded p-2 overflow-x-auto text-orange-700">
                                {r.error_message}
                              </pre>
                            </div>
                          )}

                          {/* AI explain button for FAIL/ERROR rows */}
                          {(r.status === 'FAIL' || r.status === 'ERROR') && (
                            <div className="sm:col-span-2">
                              {!mergedExplanations[r.id] && (
                                <button
                                  onClick={(e) => { e.stopPropagation(); handleExplain(r.id) }}
                                  disabled={explaining[r.id]}
                                  className="flex items-center gap-1.5 text-xs text-purple-600 hover:text-purple-800 font-medium disabled:opacity-50"
                                >
                                  {explaining[r.id] ? <Spinner /> : <span>✦</span>}
                                  {explaining[r.id] ? 'Analyzing…' : 'Explain with AI'}
                                </button>
                              )}
                              {explainErrors[r.id] && (
                                <p className="text-xs text-red-600">{explainErrors[r.id]}</p>
                              )}
                              {mergedExplanations[r.id] && (
                                <FailureAnalysisCard analysis={mergedExplanations[r.id]} />
                              )}
                            </div>
                          )}
                        </div>
                      </td>
                    </tr>
                  )}
                </>
              ))}

              {sorted.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-4 py-8 text-center text-gray-400 text-sm">
                    No results match the selected filter.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

function FailureAnalysisCard({ analysis }: { analysis: FailureAnalysis }) {
  const style = SEVERITY_STYLES[analysis.severity] ?? 'bg-gray-50 border-gray-200 text-gray-700'
  return (
    <div className={`rounded-lg border p-3 space-y-2 text-xs ${style}`}>
      <div className="flex items-center gap-2">
        <span className="font-semibold">✦ AI Analysis</span>
        <span className={`px-1.5 py-0.5 rounded text-xs font-medium capitalize ${style}`}>
          {analysis.severity}
        </span>
      </div>
      <p>
        <span className="font-medium">Likely cause:</span> {analysis.likely_cause}
      </p>
      <p className="leading-relaxed">{analysis.explanation}</p>
      {analysis.investigate.length > 0 && (
        <div>
          <p className="font-medium mb-1">Investigate:</p>
          <ul className="space-y-0.5">
            {analysis.investigate.map((item, i) => (
              <li key={i} className="flex gap-1.5">
                <span className="opacity-60">→</span>
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
