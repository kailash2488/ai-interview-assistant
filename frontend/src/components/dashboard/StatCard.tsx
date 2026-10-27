import type { ReactNode } from 'react'
import { cn } from '../../lib/utils'

/** One headline number. `change` shows an arrow and a sign, never colour alone. */
export function StatCard({ label, value, hint, icon, change }: { label: string; value: ReactNode; hint?: string; icon: ReactNode; change?: number | null }) {
  return (
    <div className="group rounded-2xl border border-slate-200/80 bg-white p-5 shadow-card transition-all duration-200 hover:-translate-y-1 hover:border-brand-200 hover:shadow-lift">
      <div className="flex items-center justify-between">
        <p className="text-sm font-medium text-slate-500">{label}</p>
        <span className="flex size-10 items-center justify-center rounded-xl bg-brand-50 text-brand-600 transition-colors group-hover:bg-brand-600 group-hover:text-white">{icon}</span>
      </div>
      <p className="mt-3 text-3xl font-semibold tabular-nums tracking-tight text-slate-900">{value}</p>
      <p className="mt-1 flex min-h-5 items-center gap-2 text-xs text-slate-500">
        {change !== undefined && change !== null && change !== 0 && (
          <span className={cn('font-medium', change > 0 ? 'text-emerald-700' : 'text-red-700')}>
            {change > 0 ? `▲ +${change}` : `▼ ${change}`}
          </span>
        )}
        {change === 0 && <span className="font-medium text-slate-500">no change</span>}
        {hint}
      </p>
    </div>
  )
}
