import { useState } from 'react'
import type { ConnectionConfig, TableEntry, GeneratedTestCase } from '../types'
import { generateTest } from '../api'

interface Props {
  sourceConn: ConnectionConfig
  targetConn: ConnectionConfig
  tablePairs: TableEntry[]
  onGenerated: (tc: GeneratedTestCase) => void
}

export default function AITestGenerator({ sourceConn, targetConn, tablePairs, onGenerated }: Props) {
  const [open, setOpen] = useState(false)
  const [prompt, setPrompt] = useState('')
  const [selectedTable, setSelectedTable] = useState<string>('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleGenerate = async () => {
    if (!prompt.trim()) return
    setLoading(true)
    setError(null)
    try {
      const tablePair = tablePairs.find((t) => t.source === selectedTable) ?? undefined
      const tc = await generateTest({
        source_conn: sourceConn,
        target_conn: targetConn,
        table_pair: tablePair,
        prompt: prompt.trim(),
      })
      onGenerated(tc)
      setOpen(false)
      setPrompt('')
      setSelectedTable('')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'AI generation failed')
    } finally {
      setLoading(false)
    }
  }

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="flex items-center gap-1.5 text-xs text-purple-600 hover:text-purple-800 font-medium"
      >
        <span>✦</span> Generate with AI
      </button>
    )
  }

  return (
    <div className="mt-3 rounded-lg border border-purple-200 bg-purple-50 p-4 space-y-3">
      <div className="flex items-center justify-between">
        <p className="text-xs font-semibold text-purple-800">Generate test with AI</p>
        <button
          onClick={() => { setOpen(false); setError(null) }}
          className="text-purple-400 hover:text-purple-700 text-lg leading-none"
        >
          ×
        </button>
      </div>

      <div>
        <label className="block text-xs font-medium text-purple-700 mb-1">
          Describe the test in plain English
        </label>
        <textarea
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          placeholder='e.g. "ensure revenue totals match within 1%" or "check that all user IDs are present"'
          rows={3}
          className="w-full border border-purple-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-purple-500 bg-white resize-none"
        />
      </div>

      {tablePairs.length > 0 && (
        <div>
          <label className="block text-xs font-medium text-purple-700 mb-1">
            Table for schema context (optional)
          </label>
          <select
            value={selectedTable}
            onChange={(e) => setSelectedTable(e.target.value)}
            className="border border-purple-300 rounded px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-purple-500 bg-white"
          >
            <option value="">— none —</option>
            {tablePairs.map((t) => (
              <option key={t.source} value={t.source}>
                {t.source} → {t.target}
              </option>
            ))}
          </select>
        </div>
      )}

      {error && (
        <p className="text-xs text-red-600 bg-red-50 border border-red-200 rounded px-2 py-1">
          {error}
        </p>
      )}

      <button
        onClick={handleGenerate}
        disabled={!prompt.trim() || loading}
        className="px-4 py-1.5 bg-purple-600 text-white text-sm font-medium rounded-lg hover:bg-purple-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors flex items-center gap-2"
      >
        {loading && (
          <svg className="animate-spin h-3.5 w-3.5" viewBox="0 0 24 24" fill="none">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
          </svg>
        )}
        {loading ? 'Generating…' : 'Generate'}
      </button>
    </div>
  )
}
