import { useState } from 'react'
import { formatDate } from '../../lib/utils'

export interface TrendPointData {
  id: string
  label: string
  date: string
  score: number
}

const W = 640
const H = 300
const M = { left: 38, right: 54, top: 18, bottom: 34 }
const LINE = '#2a78d6' // single series, one hue

/** Score over attempts. Line chart: 2px line, 10px markers with a surface ring, hairline grid, the latest value labelled
 *  at the line end, a tooltip on hover and keyboard focus, and the same numbers available as a table. */
export function TrendChart({ points }: { points: TrendPointData[] }) {
  const [active, setActive] = useState<number | null>(null)
  const [asTable, setAsTable] = useState(false)
  const innerW = W - M.left - M.right
  const innerH = H - M.top - M.bottom
  const x = (i: number) => M.left + (points.length === 1 ? innerW / 2 : (i / (points.length - 1)) * innerW)
  const y = (v: number) => M.top + innerH - (Math.max(0, Math.min(100, v)) / 100) * innerH
  const path = points.map((p, i) => `${i === 0 ? 'M' : 'L'}${x(i).toFixed(1)},${y(p.score).toFixed(1)}`).join(' ')
  const labelEvery = Math.ceil(points.length / 6)
  const last = points[points.length - 1]
  const tip = active !== null ? points[active] : null

  function nearest(clientX: number, el: SVGSVGElement) {
    const rect = el.getBoundingClientRect()
    const vx = ((clientX - rect.left) / rect.width) * W
    let best = 0
    points.forEach((_, i) => {
      if (Math.abs(x(i) - vx) < Math.abs(x(best) - vx)) best = i
    })
    setActive(best)
  }

  return (
    <figure className="flex h-full flex-1 flex-col gap-3">
      <div className="flex items-center justify-between">
        <figcaption className="text-base font-semibold text-slate-900">Score over time</figcaption>
        <button type="button" onClick={() => setAsTable((v) => !v)} className="text-xs text-slate-500 underline hover:text-slate-700">
          {asTable ? 'Show chart' : 'Show table'}
        </button>
      </div>

      {asTable ? (
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs text-slate-500">
              <th className="py-1 font-medium">Interview</th>
              <th className="py-1 font-medium">Date</th>
              <th className="py-1 font-medium">Score</th>
            </tr>
          </thead>
          <tbody>
            {points.map((p) => (
              <tr key={p.id} className="border-t border-slate-100">
                <td className="py-1.5 text-slate-800">{p.label}</td>
                <td className="py-1.5 text-slate-500">{formatDate(p.date)}</td>
                <td className="py-1.5 tabular-nums text-slate-800">{p.score}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <div className="flex flex-1 items-center">
        <div className="relative w-full">
          <svg
            viewBox={`0 0 ${W} ${H}`}
            role="img"
            aria-label={`Score over time: ${points.length} interview${points.length === 1 ? '' : 's'}, latest ${last.score} out of 100`}
            className="h-auto w-full touch-none select-none"
            onPointerMove={(e) => nearest(e.clientX, e.currentTarget)}
            onPointerLeave={() => setActive(null)}
          >
            {[0, 50, 100].map((t) => (
              <g key={t}>
                <line x1={M.left} x2={W - M.right} y1={y(t)} y2={y(t)} stroke="#e2e8f0" strokeWidth={1} />
                <text x={M.left - 8} y={y(t) + 4} textAnchor="end" className="fill-slate-400 text-[11px]">
                  {t}
                </text>
              </g>
            ))}
            {tip && <line x1={x(active!)} x2={x(active!)} y1={M.top} y2={M.top + innerH} stroke="#94a3b8" strokeWidth={1} />}
            {points.length > 1 && <path d={path} fill="none" stroke={LINE} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />}
            {points.map((p, i) => (
              <g key={p.id}>
                <circle cx={x(i)} cy={y(p.score)} r={5} fill={LINE} stroke="#fff" strokeWidth={2} />
                {/* a bigger invisible target so the point is easy to hit and to focus */}
                <circle
                  cx={x(i)}
                  cy={y(p.score)}
                  r={16}
                  fill="transparent"
                  tabIndex={0}
                  aria-label={`${p.label}, ${formatDate(p.date)}: ${p.score} out of 100`}
                  onFocus={() => setActive(i)}
                  onBlur={() => setActive(null)}
                  className="outline-none focus-visible:stroke-slate-500 focus-visible:stroke-2"
                />
                {i % labelEvery === 0 && (
                  <text x={x(i)} y={H - 10} textAnchor="middle" className="fill-slate-400 text-[11px]">
                    {new Date(p.date).toLocaleDateString(undefined, { day: 'numeric', month: 'short' })}
                  </text>
                )}
              </g>
            ))}
            <text x={x(points.length - 1) + 12} y={y(last.score) + 5} className="fill-slate-900 text-[14px] font-semibold">
              {last.score}
            </text>
          </svg>
          {tip && (
            <div
              role="tooltip"
              className="pointer-events-none absolute z-10 -translate-x-1/2 whitespace-nowrap rounded-lg bg-slate-900 px-3 py-1.5 text-xs text-white shadow-lg"
              style={{ left: `${(x(active!) / W) * 100}%`, top: `${(Math.max(y(tip.score) - 54, 0) / H) * 100}%` }}
            >
              <strong className="mr-1.5 text-sm font-semibold">{tip.score}</strong>
              <span className="text-slate-300">
                {tip.label} · {formatDate(tip.date)}
              </span>
            </div>
          )}
        </div>
        </div>
      )}
    </figure>
  )
}
