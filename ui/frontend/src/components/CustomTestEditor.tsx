import type { CustomTestEntry, ConnectionConfig, TableEntry, GeneratedTestCase } from '../types'
import AITestGenerator from './AITestGenerator'

interface Props {
  tests: CustomTestEntry[]
  onChange: (tests: CustomTestEntry[]) => void
  // Optional: enables "Generate with AI" when provided
  sourceConn?: ConnectionConfig
  targetConn?: ConnectionConfig
  tablePairs?: TableEntry[]
}

export default function CustomTestEditor({ tests, onChange, sourceConn, targetConn, tablePairs }: Props) {
  const add = () => {
    onChange([
      ...tests,
      {
        id: crypto.randomUUID(),
        description: '',
        source_sql: '',
        target_sql: '',
        comparison_strategy: 'EXACT',
        tolerance: 0,
      },
    ])
  }

  const remove = (id: string) => onChange(tests.filter((t) => t.id !== id))

  const update = (id: string, patch: Partial<CustomTestEntry>) =>
    onChange(tests.map((t) => (t.id === id ? { ...t, ...patch } : t)))

  const applyGenerated = (id: string, tc: GeneratedTestCase) => {
    update(id, {
      description: tc.description,
      source_sql: tc.source_sql,
      target_sql: tc.target_sql,
      comparison_strategy: tc.comparison_strategy,
      tolerance: tc.tolerance,
    })
  }

  const showAI = !!(sourceConn && targetConn)

  return (
    <div className="space-y-4">
      {tests.map((test, idx) => (
        <div key={test.id} className="bg-white rounded-xl border border-gray-200 p-5 space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium text-gray-700">Custom test {idx + 1}</span>
            <button
              onClick={() => remove(test.id)}
              className="text-gray-400 hover:text-red-500 text-lg leading-none"
              title="Remove"
            >
              ×
            </button>
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">Description</label>
            <input
              type="text"
              value={test.description}
              onChange={(e) => update(test.id, { description: e.target.value })}
              placeholder="e.g. Check order count matches after migration"
              className="w-full border border-gray-300 rounded px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">Source SQL</label>
              <textarea
                value={test.source_sql}
                onChange={(e) => update(test.id, { source_sql: e.target.value })}
                placeholder="SELECT COUNT(*) FROM public.orders"
                rows={4}
                className="w-full border border-gray-300 rounded px-3 py-2 font-mono text-xs focus:outline-none focus:ring-2 focus:ring-blue-500 resize-y"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">Target SQL</label>
              <textarea
                value={test.target_sql}
                onChange={(e) => update(test.id, { target_sql: e.target.value })}
                placeholder="SELECT COUNT(*) FROM public.orders"
                rows={4}
                className="w-full border border-gray-300 rounded px-3 py-2 font-mono text-xs focus:outline-none focus:ring-2 focus:ring-blue-500 resize-y"
              />
            </div>
          </div>

          <div className="flex items-center gap-4 flex-wrap">
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">Comparison strategy</label>
              <select
                value={test.comparison_strategy}
                onChange={(e) =>
                  update(test.id, {
                    comparison_strategy: e.target.value as 'EXACT' | 'NUMERIC_TOLERANCE',
                  })
                }
                className="border border-gray-300 rounded px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="EXACT">EXACT</option>
                <option value="NUMERIC_TOLERANCE">NUMERIC_TOLERANCE</option>
              </select>
            </div>

            {test.comparison_strategy === 'NUMERIC_TOLERANCE' && (
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">Tolerance</label>
                <input
                  type="number"
                  step="any"
                  min={0}
                  value={test.tolerance}
                  onChange={(e) => update(test.id, { tolerance: Number(e.target.value) })}
                  className="w-32 border border-gray-300 rounded px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
            )}
          </div>

          {/* AI Test Generator */}
          {showAI && (
            <AITestGenerator
              sourceConn={sourceConn!}
              targetConn={targetConn!}
              tablePairs={tablePairs ?? []}
              onGenerated={(tc) => applyGenerated(test.id, tc)}
            />
          )}
        </div>
      ))}

      <button
        onClick={add}
        className="flex items-center gap-2 text-sm text-blue-600 hover:text-blue-800 font-medium"
      >
        <span className="text-lg leading-none">+</span> Add test case
      </button>
    </div>
  )
}
