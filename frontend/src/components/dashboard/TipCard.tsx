import { Lightbulb } from 'lucide-react'
import { useState } from 'react'
import { TIPS, tipOfTheDay } from './tips'

export function TipCard() {
  const [index, setIndex] = useState(tipOfTheDay())
  const tip = TIPS[index]
  return (
    <aside aria-label="Interview tip" className="flex items-start gap-4 rounded-2xl border border-amber-200 bg-gradient-to-br from-amber-50 to-white p-5">
      <span className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-amber-100 text-amber-700">
        <Lightbulb className="size-5" aria-hidden />
      </span>
      <div className="min-w-0 flex-1">
        <p className="text-xs font-semibold uppercase tracking-widest text-amber-700">Interview tip</p>
        <h3 className="mt-0.5 font-semibold text-slate-900">{tip.title}</h3>
        <p className="mt-1 text-sm leading-relaxed text-slate-600">{tip.text}</p>
      </div>
      <button type="button" onClick={() => setIndex((i) => (i + 1) % TIPS.length)} className="shrink-0 text-xs font-medium text-amber-800 underline underline-offset-2 hover:text-amber-950">
        Next tip
      </button>
    </aside>
  )
}
