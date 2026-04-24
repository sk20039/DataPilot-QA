import type { ConnectionConfig, ConnectionTestResult } from '../types'

const DIALECTS = [
  { value: 'postgresql', label: 'PostgreSQL', defaultPort: 5432 },
  { value: 'snowflake', label: 'Snowflake', defaultPort: 443 },
  { value: 'oracle', label: 'Oracle', defaultPort: 1521 },
]

interface Props {
  label: string
  value: ConnectionConfig
  onChange: (c: ConnectionConfig) => void
  onTest: () => void
  testing: boolean
  testResult: ConnectionTestResult | null
}

function Field({
  label,
  type = 'text',
  value,
  onChange,
  placeholder,
}: {
  label: string
  type?: string
  value: string | number
  onChange: (v: string) => void
  placeholder?: string
}) {
  return (
    <div>
      <label className="block text-xs font-medium text-gray-600 mb-1">{label}</label>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full border border-gray-300 rounded-md px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
      />
    </div>
  )
}

export default function ConnectionForm({ label, value, onChange, onTest, testing, testResult }: Props) {
  const set = (patch: Partial<ConnectionConfig>) => onChange({ ...value, ...patch })
  const isSnowflake = value.dialect === 'snowflake'

  const handleDialectChange = (dialect: string) => {
    const d = DIALECTS.find((x) => x.value === dialect)
    set({ dialect, port: d?.defaultPort ?? 5432 })
  }

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5 flex flex-col gap-4">
      <h2 className="font-semibold text-gray-800 text-base">{label}</h2>

      {/* Dialect */}
      <div>
        <label className="block text-xs font-medium text-gray-600 mb-1">Dialect</label>
        <select
          value={value.dialect}
          onChange={(e) => handleDialectChange(e.target.value)}
          className="w-full border border-gray-300 rounded-md px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          {DIALECTS.map((d) => (
            <option key={d.value} value={d.value}>
              {d.label}
            </option>
          ))}
        </select>
      </div>

      {/* Host / Port  (hidden for Snowflake) */}
      {!isSnowflake && (
        <div className="grid grid-cols-3 gap-3">
          <div className="col-span-2">
            <Field label="Host" value={value.host} onChange={(v) => set({ host: v })} placeholder="localhost" />
          </div>
          <Field label="Port" type="number" value={value.port} onChange={(v) => set({ port: Number(v) })} />
        </div>
      )}

      {/* Account (Snowflake only) */}
      {isSnowflake && (
        <Field
          label="Account"
          value={value.account}
          onChange={(v) => set({ account: v })}
          placeholder="org-account"
        />
      )}

      <Field label="Database" value={value.database} onChange={(v) => set({ database: v })} placeholder="my_database" />

      <div className="grid grid-cols-2 gap-3">
        <Field label="Username" value={value.username} onChange={(v) => set({ username: v })} />
        <Field label="Password" type="password" value={value.password} onChange={(v) => set({ password: v })} />
      </div>

      <Field
        label="Schema (optional)"
        value={value.schema_name}
        onChange={(v) => set({ schema_name: v })}
        placeholder="public"
      />

      {/* Test button + result */}
      <div className="flex items-center gap-3 pt-1">
        <button
          onClick={onTest}
          disabled={testing}
          className="px-4 py-1.5 text-sm font-medium rounded-md bg-gray-100 hover:bg-gray-200 disabled:opacity-50 transition-colors"
        >
          {testing ? 'Testing…' : 'Test Connection'}
        </button>

        {testResult && (
          <span
            className={`text-sm font-medium ${
              testResult.ok ? 'text-green-600' : 'text-red-600'
            }`}
          >
            {testResult.ok ? `✓ Connected — ${testResult.tables?.length ?? 0} tables found` : `✗ ${testResult.error}`}
          </span>
        )}
      </div>
    </div>
  )
}
