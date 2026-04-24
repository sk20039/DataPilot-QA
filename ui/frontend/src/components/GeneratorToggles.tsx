import type { GeneratorsConfig, GeneratorSetting } from '../types'

const GENERATORS: {
  key: keyof GeneratorsConfig
  name: string
  description: string
  hasTolerance: boolean
}[] = [
  {
    key: 'row_count',
    name: 'Row Count',
    description: 'Compares total row counts between source and target.',
    hasTolerance: false,
  },
  {
    key: 'schema_check',
    name: 'Schema Check',
    description: 'Validates column names, data types, and nullability.',
    hasTolerance: false,
  },
  {
    key: 'field_match',
    name: 'Field Match',
    description: 'Compares actual field values row-by-row.',
    hasTolerance: false,
  },
  {
    key: 'null_duplicate',
    name: 'Nulls & Duplicates',
    description: 'Detects unexpected NULL values and duplicate records.',
    hasTolerance: false,
  },
  {
    key: 'aggregate_recon',
    name: 'Aggregate Reconciliation',
    description: 'Compares SUM, AVG, and COUNT aggregates for numeric columns.',
    hasTolerance: true,
  },
  {
    key: 'missing_rows',
    name: 'Missing Row Detection',
    description: 'Identifies which primary key values are missing in the target. Shows exact IDs.',
    hasTolerance: false,
  },
]

interface Props {
  value: GeneratorsConfig
  onChange: (g: GeneratorsConfig) => void
}

function Toggle({ on, onToggle }: { on: boolean; onToggle: () => void }) {
  return (
    <button
      role="switch"
      aria-checked={on}
      onClick={onToggle}
      className={`relative inline-flex h-5 w-9 shrink-0 rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-1 ${
        on ? 'bg-blue-600' : 'bg-gray-300'
      }`}
    >
      <span
        className={`inline-block h-4 w-4 mt-0.5 rounded-full bg-white shadow transition-transform ${
          on ? 'translate-x-4' : 'translate-x-0.5'
        }`}
      />
    </button>
  )
}

export default function GeneratorToggles({ value, onChange }: Props) {
  const set = (key: keyof GeneratorsConfig, patch: Partial<GeneratorSetting>) =>
    onChange({ ...value, [key]: { ...value[key], ...patch } })

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5">
      <h2 className="font-semibold text-gray-800 text-base mb-4">Validation Checks</h2>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {GENERATORS.map(({ key, name, description, hasTolerance }) => {
          const setting = value[key]
          return (
            <div
              key={key}
              className={`rounded-lg border p-4 flex flex-col gap-3 transition-colors ${
                setting.enabled ? 'border-blue-200 bg-blue-50' : 'border-gray-200 bg-gray-50'
              }`}
            >
              <div className="flex items-start justify-between gap-2">
                <div>
                  <p className="text-sm font-medium text-gray-800">{name}</p>
                  <p className="text-xs text-gray-500 mt-0.5">{description}</p>
                </div>
                <Toggle on={setting.enabled} onToggle={() => set(key, { enabled: !setting.enabled })} />
              </div>

              {hasTolerance && setting.enabled && (
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">
                    Tolerance
                  </label>
                  <input
                    type="number"
                    step="any"
                    value={setting.tolerance}
                    onChange={(e) => set(key, { tolerance: Number(e.target.value) })}
                    className="w-full border border-gray-300 rounded px-2 py-1 text-xs focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
