import { ArrowRight, FileUp, Flag, MessageSquareText, PlayCircle, Plus, Search, Sparkles } from 'lucide-react'
import { Link } from 'react-router-dom'
import type { Dashboard } from '../../lib/api'
import { buttonClasses } from '../ui/button'

const ICONS = { new: Plus, upload: FileUp, analyse: Search, plan: Sparkles, start: PlayCircle, continue: MessageSquareText, report: Flag }

/** The one thing worth doing next, decided by where the user's latest interview stands. */
export function NextActionCard({ action }: { action: Dashboard['next_action'] }) {
  const Icon = ICONS[action.kind]
  return (
    <section aria-label="Suggested next step" className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-brand-700 via-brand-600 to-fuchsia-600 p-7 text-white shadow-lift sm:p-8">
      <div aria-hidden className="absolute -right-16 -top-16 size-64 rounded-full bg-white/10 blur-2xl" />
      <div className="relative flex flex-wrap items-center justify-between gap-6">
        <div className="flex max-w-xl items-start gap-4">
          <span className="flex size-12 shrink-0 items-center justify-center rounded-2xl bg-white/15 ring-1 ring-white/25">
            <Icon className="size-6" aria-hidden />
          </span>
          <div>
            <p className="text-xs font-semibold uppercase tracking-widest text-brand-200">Next step</p>
            <h2 className="mt-1 text-2xl font-semibold tracking-tight">{action.label}</h2>
            <p className="mt-1.5 text-sm text-brand-100">{action.description}</p>
          </div>
        </div>
        <Link to={action.href} className={buttonClasses('secondary', 'lg', 'border-transparent')}>
          {action.kind === 'new' ? 'Get started' : 'Continue'} <ArrowRight className="size-4" aria-hidden />
        </Link>
      </div>
    </section>
  )
}
