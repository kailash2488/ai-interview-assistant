import { ChevronDown, ChevronRight } from 'lucide-react'
import { useState } from 'react'
import type { QuestionReport } from '../lib/api'
import { Badge } from './ui/badge'

export const DIMENSION_LABELS: Record<string, string> = {
  technical_accuracy: 'Technical accuracy',
  depth: 'Depth',
  relevance: 'Relevance',
  structure_clarity: 'Structure and clarity',
  evidence: 'Evidence',
}

const tone = (pct: number) => (pct >= 70 ? 'success' : pct >= 45 ? 'info' : 'danger')

export function QuestionCard({ q }: { q: QuestionReport }) {
  const [open, setOpen] = useState(false)
  return (
    <li className="rounded-lg border border-slate-200 bg-white">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex w-full items-center gap-3 px-4 py-3 text-left"
      >
        {open ? <ChevronDown className="size-4 shrink-0 text-slate-400" /> : <ChevronRight className="size-4 shrink-0 text-slate-400" />}
        <span className="min-w-0 flex-1">
          <span className="block truncate text-sm font-medium text-slate-900">
            {q.order_no}. {q.topic}
            {q.is_follow_up && <span className="ml-2 text-xs font-normal text-slate-400">follow-up</span>}
          </span>
          <span className="block truncate text-xs text-slate-500">{q.answer_summary}</span>
        </span>
        <Badge tone={tone(q.score_percent)}>{q.score_percent}/100</Badge>
      </button>

      {open && (
        <div className="space-y-4 border-t border-slate-100 px-4 py-4 text-sm">
          <section>
            <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Question</h4>
            <p className="mt-1 text-slate-800">{q.question}</p>
          </section>
          <section>
            <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Your answer</h4>
            <p className="mt-1 whitespace-pre-wrap rounded-md bg-slate-50 p-3 text-slate-700">{q.answer}</p>
          </section>
          <section>
            <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Feedback</h4>
            <p className="mt-1 text-slate-800">{q.feedback}</p>
          </section>
          {q.missing_points.length > 0 && (
            <section>
              <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-500">What was missing</h4>
              <ul className="mt-1 list-inside list-disc text-slate-700">
                {q.missing_points.map((m) => (
                  <li key={m}>{m}</li>
                ))}
              </ul>
            </section>
          )}
          <section>
            <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Scores and evidence</h4>
            <table className="mt-1 w-full">
              <tbody>
                {Object.entries(q.dimensions).map(([key, d]) => (
                  <tr key={key} className="border-t border-slate-100 align-top">
                    <td className="py-1.5 pr-3 text-slate-700">{DIMENSION_LABELS[key] ?? key}</td>
                    <td className="py-1.5 pr-3 whitespace-nowrap font-medium tabular-nums text-slate-900">{d.score} / 5</td>
                    <td className="py-1.5 text-slate-500">{d.quote ? `“${d.quote}”` : 'No supporting quote'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
          {q.notes.length > 0 && (
            <ul className="space-y-1 rounded-md bg-amber-50 p-3 text-xs text-amber-800">
              {q.notes.map((n) => (
                <li key={n}>{n}</li>
              ))}
            </ul>
          )}
          {q.sample_answer && (
            <section>
              <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-500">A stronger answer</h4>
              <p className="mt-1 whitespace-pre-wrap rounded-md bg-emerald-50 p-3 text-slate-800">{q.sample_answer}</p>
            </section>
          )}
        </div>
      )}
    </li>
  )
}
