import { useState } from 'react'
import type { RunSummary } from '../types'

interface Props {
  summary: RunSummary
}

const STATUS_STYLES: Record<RunSummary['overall_status'], string> = {
  PASS: 'bg-green-100 text-green-800 border-green-300',
  FAIL: 'bg-red-100 text-red-800 border-red-300',
  CAUTION: 'bg-yellow-100 text-yellow-800 border-yellow-300',
}

const REC_STYLES: Record<RunSummary['recommendation'], string> = {
  'Go': 'bg-green-600 text-white',
  'No-Go': 'bg-red-600 text-white',
  'Investigate further': 'bg-yellow-500 text-white',
}

function RiskBadge({ score }: { score: number }) {
  const color =
    score < 30 ? 'bg-green-100 text-green-800' :
    score < 70 ? 'bg-yellow-100 text-yellow-800' :
    'bg-red-100 text-red-800'
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold ${color}`}>
      Risk {score}/100
    </span>
  )
}

export default function AISummaryPanel({ summary }: Props) {
  const [expanded, setExpanded] = useState(false)

  return (
    <div className={`rounded-xl border-2 p-5 space-y-4 ${STATUS_STYLES[summary.overall_status]}`}>
      {/* Header row */}
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div className="flex items-center gap-3 flex-wrap">
          <span className={`px-3 py-1 rounded-full text-sm font-bold border ${STATUS_STYLES[summary.overall_status]}`}>
            {summary.overall_status}
          </span>
          <RiskBadge score={summary.risk_score} />
          <span className={`px-3 py-1 rounded-full text-xs font-semibold ${REC_STYLES[summary.recommendation]}`}>
            {summary.recommendation}
          </span>
        </div>
        <button
          onClick={() => setExpanded(!expanded)}
          className="text-xs underline underline-offset-2 opacity-70 hover:opacity-100"
        >
          {expanded ? 'Show less' : 'Show more'}
        </button>
      </div>

      {/* Headline */}
      <p className="font-semibold text-base">{summary.headline}</p>

      {/* Key findings */}
      {summary.key_findings.length > 0 && (
        <ul className="space-y-1">
          {summary.key_findings.map((f, i) => (
            <li key={i} className="text-sm flex gap-2">
              <span className="opacity-60">•</span>
              <span>{f}</span>
            </li>
          ))}
        </ul>
      )}

      {/* Expanded: patterns + narrative */}
      {expanded && (
        <div className="space-y-3 border-t border-current border-opacity-20 pt-3">
          {summary.patterns.length > 0 && (
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide opacity-70 mb-1">Patterns</p>
              <ul className="space-y-1">
                {summary.patterns.map((p, i) => (
                  <li key={i} className="text-sm flex gap-2">
                    <span className="opacity-60">↳</span>
                    <span>{p}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide opacity-70 mb-1">Details</p>
            <p className="text-sm leading-relaxed whitespace-pre-line">{summary.details}</p>
          </div>
        </div>
      )}
    </div>
  )
}
