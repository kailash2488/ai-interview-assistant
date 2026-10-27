import type { ReactNode } from 'react'
import { cn } from '../../lib/utils'

export type Tone = 'neutral' | 'info' | 'success' | 'danger' | 'brand'

const TONES: Record<Tone, string> = {
  neutral: 'bg-slate-100 text-slate-700 ring-slate-200',
  info: 'bg-sky-50 text-sky-800 ring-sky-200',
  success: 'bg-emerald-50 text-emerald-800 ring-emerald-200',
  danger: 'bg-red-50 text-red-800 ring-red-200',
  brand: 'bg-brand-50 text-brand-700 ring-brand-200',
}

export function Badge({ tone = 'neutral', children }: { tone?: Tone; children: ReactNode }) {
  return (
    <span className={cn('inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset', TONES[tone])}>
      {children}
    </span>
  )
}
