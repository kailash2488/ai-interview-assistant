import type { InputHTMLAttributes, ReactNode, SelectHTMLAttributes, TextareaHTMLAttributes } from 'react'
import { cn } from '../../lib/utils'

const CONTROL =
  'w-full rounded-xl border border-slate-200 bg-white px-3.5 py-2.5 text-sm text-slate-900 shadow-sm placeholder:text-slate-400 transition-colors ' +
  'hover:border-slate-300 focus:border-brand-500 focus:outline-none focus:ring-4 focus:ring-brand-500/15 disabled:bg-slate-50 disabled:text-slate-400'

export function Field({ label, hint, error, children }: { label: string; hint?: string; error?: string | null; children: ReactNode }) {
  return (
    <div className="space-y-1.5">
      <label className="block space-y-1.5">
        <span className="text-sm font-medium text-slate-700">{label}</span>
        {children}
      </label>
      {error ? (
        <p role="alert" className="text-xs text-red-600">
          {error}
        </p>
      ) : (
        hint && <p className="text-xs text-slate-500">{hint}</p>
      )}
    </div>
  )
}

export const Input = (props: InputHTMLAttributes<HTMLInputElement>) => <input {...props} className={cn(CONTROL, props.className)} />

export const Select = (props: SelectHTMLAttributes<HTMLSelectElement>) => <select {...props} className={cn(CONTROL, 'pr-9', props.className)} />

export const Textarea = (props: TextareaHTMLAttributes<HTMLTextAreaElement>) => <textarea {...props} className={cn(CONTROL, props.className)} />
