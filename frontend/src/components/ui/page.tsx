import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'

export function PageHeader({ title, subtitle, back, actions }: { title: string; subtitle?: ReactNode; back?: { to: string; label: string }; actions?: ReactNode }) {
  return (
    <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
      <div>
        {back && (
          <Link to={back.to} className="mb-2 inline-flex items-center gap-1 text-sm text-slate-500 transition-colors hover:text-slate-800">
            <span aria-hidden>←</span> {back.label}
          </Link>
        )}
        <h1 className="text-3xl font-semibold tracking-tight text-slate-900">{title}</h1>
        {subtitle && <p className="mt-1.5 max-w-2xl text-sm text-slate-500">{subtitle}</p>}
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </div>
  )
}
