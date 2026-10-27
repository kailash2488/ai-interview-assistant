import { Check } from 'lucide-react'
import { Link } from 'react-router-dom'
import { cn } from '../lib/utils'

export type StepKey = 'documents' | 'analysis' | 'plan' | 'interview' | 'report'

const STEPS: Array<{ key: StepKey; label: string; path: (id: string) => string }> = [
  { key: 'documents', label: 'Documents', path: (id) => `/sessions/${id}/upload` },
  { key: 'analysis', label: 'Analysis', path: (id) => `/sessions/${id}/analysis` },
  { key: 'plan', label: 'Plan', path: (id) => `/sessions/${id}/plan` },
  { key: 'interview', label: 'Interview', path: (id) => `/sessions/${id}/interview` },
  { key: 'report', label: 'Report', path: (id) => `/sessions/${id}/report` },
]

/** Where the user is in the flow. Earlier steps are links; later steps are not yet reachable. */
export function Stepper({ sessionId, current }: { sessionId: string; current: StepKey }) {
  const index = STEPS.findIndex((s) => s.key === current)
  return (
    <nav aria-label="Progress" className="mb-8">
      <ol className="flex items-center gap-1 overflow-x-auto sm:gap-2">
        {STEPS.map((s, i) => {
          const done = i < index
          const active = i === index
          const body = (
            <span className={cn('flex items-center gap-2 whitespace-nowrap rounded-full px-3 py-1.5 text-xs font-medium sm:text-sm', active ? 'bg-brand-600 text-white shadow-sm' : done ? 'bg-brand-50 text-brand-700 hover:bg-brand-100' : 'text-slate-400')}>
              <span className={cn('flex size-5 items-center justify-center rounded-full text-[11px]', active ? 'bg-white/20' : done ? 'bg-brand-600 text-white' : 'bg-slate-100 text-slate-400')}>
                {done ? <Check className="size-3" aria-hidden /> : i + 1}
              </span>
              {s.label}
            </span>
          )
          return (
            <li key={s.key} className="flex items-center gap-1 sm:gap-2" aria-current={active ? 'step' : undefined}>
              {done ? <Link to={s.path(sessionId)}>{body}</Link> : body}
              {i < STEPS.length - 1 && <span aria-hidden className={cn('h-px w-3 sm:w-6', done ? 'bg-brand-300' : 'bg-slate-200')} />}
            </li>
          )
        })}
      </ol>
    </nav>
  )
}
