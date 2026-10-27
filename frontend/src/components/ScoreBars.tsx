import { useState } from 'react'

export interface Bar {
  label: string
  value: number // 0-100
  detail?: string // shown in the tooltip and the table
}

const BAR = '#2a78d6' // single series, one hue; the label next to it carries the name (text never wears the data colour)

/** Horizontal bar chart for one measure across categories. Single series, so no legend: the title names it. */
export function ScoreBars({ title, bars, valueLabel = 'Score' }: { title: string; bars: Bar[]; valueLabel?: string }) {
  const [active, setActive] = useState<number | null>(null)
  const [asTable, setAsTable] = useState(false)

  return (
    <figure className="space-y-3">
      <div className="flex items-center justify-between">
        <figcaption className="text-base font-semibold text-slate-900">{title}</figcaption>
        <button type="button" onClick={() => setAsTable((v) => !v)} className="text-xs text-slate-500 underline hover:text-slate-700">
          {asTable ? 'Show chart' : 'Show table'}
        </button>
      </div>

      {asTable ? (
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs text-slate-500">
              <th className="py-1 font-medium">Category</th>
              <th className="py-1 font-medium">{valueLabel}</th>
              <th className="py-1 font-medium">Detail</th>
            </tr>
          </thead>
          <tbody>
            {bars.map((b) => (
              <tr key={b.label} className="border-t border-slate-100">
                <td className="py-1.5 text-slate-800">{b.label}</td>
                <td className="py-1.5 tabular-nums text-slate-800">{b.value}</td>
                <td className="py-1.5 text-slate-500">{b.detail ?? ''}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <div role="list" aria-label={title} className="relative space-y-2.5">
          {bars.map((b, i) => (
            <div key={b.label} role="listitem" className="relative grid grid-cols-[9.5rem_1fr_2.5rem] items-center gap-3">
              <span className="truncate text-sm text-slate-700" title={b.label}>
                {b.label}
              </span>
              <div
                tabIndex={0}
                aria-label={`${b.label}: ${b.value} out of 100${b.detail ? `, ${b.detail}` : ''}`}
                onPointerEnter={() => setActive(i)}
                onPointerLeave={() => setActive(null)}
                onFocus={() => setActive(i)}
                onBlur={() => setActive(null)}
                className="relative flex h-6 items-center rounded outline-offset-2 focus-visible:outline-2 focus-visible:outline-slate-400"
              >
                {[0, 50, 100].map((tick) => (
                  <span key={tick} aria-hidden className="absolute inset-y-0 w-px bg-slate-200" style={{ left: `${tick === 100 ? 99.6 : tick}%` }} />
                ))}
                <span
                  aria-hidden
                  className="relative block h-4 rounded-r-[4px] transition-[filter]"
                  style={{ width: `${Math.max(0, Math.min(100, b.value))}%`, background: BAR, filter: active === i ? 'brightness(1.12)' : undefined }}
                />
                {active === i && (
                  <span
                    role="tooltip"
                    className="pointer-events-none absolute -top-9 z-10 whitespace-nowrap rounded-md bg-slate-900 px-2.5 py-1 text-xs text-white shadow"
                    style={{ left: `${Math.min(Math.max(b.value, 8), 80)}%` }}
                  >
                    <strong className="font-semibold">{b.value}</strong> <span className="text-slate-300">{b.label}{b.detail ? ` · ${b.detail}` : ''}</span>
                  </span>
                )}
              </div>
              <span className="text-right text-sm font-medium tabular-nums text-slate-900">{b.value}</span>
            </div>
          ))}
          <div aria-hidden className="grid grid-cols-[9.5rem_1fr_2.5rem] gap-3 text-xs text-slate-400">
            <span />
            <div className="flex justify-between">
              <span>0</span>
              <span>50</span>
              <span>100</span>
            </div>
            <span />
          </div>
        </div>
      )}
    </figure>
  )
}
