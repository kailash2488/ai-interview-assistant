import { cn } from '../../lib/utils'

interface Props<T extends string> {
  label: string
  value: T
  options: Array<{ value: T; label: string; hint?: string }>
  onChange: (value: T) => void
}

/** A small set of mutually exclusive choices shown as buttons (clearer than a drop-down for 2 to 4 options). */
export function Segmented<T extends string>({ label, value, options, onChange }: Props<T>) {
  return (
    <fieldset className="space-y-1.5">
      <legend className="text-sm font-medium text-slate-700">{label}</legend>
      <div className="grid gap-2" style={{ gridTemplateColumns: `repeat(${options.length}, minmax(0, 1fr))` }} role="radiogroup" aria-label={label}>
        {options.map((o) => (
          <button
            key={o.value}
            type="button"
            role="radio"
            aria-checked={value === o.value}
            onClick={() => onChange(o.value)}
            className={cn(
              'rounded-xl border px-3 py-2.5 text-left text-sm transition-all focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-500',
              value === o.value ? 'border-brand-500 bg-brand-50 text-brand-800 ring-4 ring-brand-500/10' : 'border-slate-200 bg-white text-slate-700 hover:border-slate-300',
            )}
          >
            <span className="block font-medium">{o.label}</span>
            {o.hint && <span className="mt-0.5 block text-xs text-slate-500">{o.hint}</span>}
          </button>
        ))}
      </div>
    </fieldset>
  )
}
