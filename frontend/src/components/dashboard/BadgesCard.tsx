import { Award, Lock } from 'lucide-react'
import type { Dashboard } from '../../lib/api'
import { cn } from '../../lib/utils'
import { Card } from '../ui/card'

export function BadgesCard({ badges }: { badges: Dashboard['badges'] }) {
  const earned = badges.filter((b) => b.earned).length
  return (
    <Card className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold text-slate-900">Milestones</h2>
        <span className="text-sm text-slate-500">
          {earned} of {badges.length}
        </span>
      </div>
      <ul className="grid grid-cols-2 gap-3">
        {badges.map((b) => (
          <li
            key={b.id}
            title={b.description}
            className={cn('flex items-start gap-3 rounded-xl border p-3', b.earned ? 'border-brand-200 bg-brand-50/60' : 'border-slate-200 bg-slate-50/60')}
          >
            <span className={cn('flex size-8 shrink-0 items-center justify-center rounded-full', b.earned ? 'bg-gradient-to-br from-brand-500 to-fuchsia-500 text-white' : 'bg-slate-200 text-slate-400')}>
              {b.earned ? <Award className="size-4" aria-hidden /> : <Lock className="size-3.5" aria-hidden />}
            </span>
            <span className="min-w-0">
              <span className={cn('block text-sm font-medium', b.earned ? 'text-slate-900' : 'text-slate-500')}>{b.label}</span>
              <span className="block text-xs text-slate-500">{b.earned ? 'Earned' : b.description}</span>
            </span>
          </li>
        ))}
      </ul>
    </Card>
  )
}
