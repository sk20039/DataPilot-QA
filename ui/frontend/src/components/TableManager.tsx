import { useState } from 'react'
import type { TableEntry } from '../types'

interface Props {
  tables: TableEntry[]
  onChange: (tables: TableEntry[]) => void
  sourceTables: string[]
  targetTables: string[]
}

function TableSelect({
  value,
  options,
  onChange,
  placeholder,
}: {
  value: string
  options: string[]
  onChange: (v: string) => void
  placeholder: string
}) {
  if (options.length === 0) {
    return (
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="flex-1 border border-gray-300 rounded-md px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
      />
    )
  }
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="flex-1 border border-gray-300 rounded-md px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
    >
      <option value="">{placeholder}</option>
      {options.map((t) => (
        <option key={t} value={t}>
          {t}
        </option>
      ))}
    </select>
  )
}

export default function TableManager({ tables, onChange, sourceTables, targetTables }: Props) {
  const [newSrc, setNewSrc] = useState('')
  const [newTgt, setNewTgt] = useState('')
  const [newPk, setNewPk] = useState('')

  const addPair = () => {
    if (!newSrc.trim() || !newTgt.trim()) return
    onChange([...tables, { source: newSrc.trim(), target: newTgt.trim(), primaryKey: newPk.trim() || undefined }])
    setNewSrc('')
    setNewTgt('')
    setNewPk('')
  }

  const updatePk = (i: number, pk: string) => {
    const updated = tables.map((t, idx) => idx === i ? { ...t, primaryKey: pk || undefined } : t)
    onChange(updated)
  }

  const removePair = (i: number) => {
    onChange(tables.filter((_, idx) => idx !== i))
  }

  const autoPopulate = () => {
    // Auto-match tables by name (exact match only)
    const tgtSet = new Set(targetTables)
    const matched: TableEntry[] = sourceTables
      .filter((t) => tgtSet.has(t))
      .map((t) => ({ source: t, target: t, primaryKey: undefined }))
    if (matched.length > 0) onChange(matched)
  }

  const hint = sourceTables.length === 0 ? 'Test source connection first to browse tables' : null

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5">
      <div className="flex items-center justify-between mb-4">
        <h2 className="font-semibold text-gray-800 text-base">Tables to Validate</h2>
        {sourceTables.length > 0 && targetTables.length > 0 && (
          <button
            onClick={autoPopulate}
            className="text-xs text-blue-600 hover:text-blue-800 font-medium"
          >
            Auto-match by name
          </button>
        )}
      </div>

      {hint && <p className="text-xs text-gray-400 mb-3">{hint}</p>}

      {/* Existing pairs */}
      {tables.length > 0 && (
        <div className="mb-4 space-y-2">
          <div className="grid grid-cols-[1fr_auto_1fr_1fr_auto] gap-2 text-xs font-medium text-gray-500 px-1">
            <span>Source table</span>
            <span />
            <span>Target table</span>
            <span>Primary key column(s)</span>
            <span />
          </div>
          {tables.map((t, i) => (
            <div key={i} className="grid grid-cols-[1fr_auto_1fr_1fr_auto] gap-2 items-center">
              <span className="font-mono text-sm bg-gray-50 border border-gray-200 rounded px-2 py-1 truncate">
                {t.source}
              </span>
              <span className="text-gray-400 text-xs">→</span>
              <span className="font-mono text-sm bg-gray-50 border border-gray-200 rounded px-2 py-1 truncate">
                {t.target}
              </span>
              <input
                type="text"
                value={t.primaryKey ?? ''}
                onChange={(e) => updatePk(i, e.target.value)}
                placeholder="id"
                className="font-mono text-sm border border-gray-300 rounded px-2 py-1 focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <button
                onClick={() => removePair(i)}
                className="text-gray-400 hover:text-red-500 text-lg leading-none"
                title="Remove"
              >
                ×
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Add new pair */}
      <div className="flex gap-2 items-center">
        <TableSelect
          value={newSrc}
          options={sourceTables}
          onChange={(v) => {
            setNewSrc(v)
            // Auto-fill target if it matches
            if (targetTables.includes(v)) setNewTgt(v)
          }}
          placeholder="Source table"
        />
        <span className="text-gray-400 text-xs shrink-0">→</span>
        <TableSelect
          value={newTgt}
          options={targetTables}
          onChange={setNewTgt}
          placeholder="Target table"
        />
        <input
          type="text"
          value={newPk}
          onChange={(e) => setNewPk(e.target.value)}
          placeholder="Primary key (e.g. id)"
          className="flex-1 border border-gray-300 rounded-md px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
        <button
          onClick={addPair}
          disabled={!newSrc.trim() || !newTgt.trim()}
          className="shrink-0 px-3 py-1.5 bg-blue-600 text-white text-sm font-medium rounded-md hover:bg-blue-700 disabled:opacity-40 transition-colors"
        >
          Add
        </button>
      </div>
    </div>
  )
}
