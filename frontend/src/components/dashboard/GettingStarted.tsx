import { ClipboardList, FileUp, MessageSquareText, Search } from 'lucide-react'
import { Card } from '../ui/card'

const STEPS = [
  { icon: FileUp, title: 'Upload', text: 'Your resume and the job description.' },
  { icon: Search, title: 'Review', text: 'Check what the AI understood and fix it.' },
  { icon: MessageSquareText, title: 'Interview', text: 'Answer one question at a time, by typing or by voice.' },
  { icon: ClipboardList, title: 'Improve', text: 'Read your report and practise your weak spots.' },
]

/** Shown until the first interview exists, so the dashboard is never an empty page. */
export function GettingStarted() {
  return (
    <Card className="space-y-5">
      <div>
        <h2 className="text-base font-semibold text-slate-900">How it works</h2>
        <p className="mt-1 text-sm text-slate-500">Your stats, trend and milestones fill in as you practise.</p>
      </div>
      <ol className="grid gap-4 sm:grid-cols-4">
        {STEPS.map((s, i) => (
          <li key={s.title} className="flex gap-3">
            <span className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-brand-50 text-brand-600">
              <s.icon className="size-5" aria-hidden />
            </span>
            <span>
              <span className="block text-sm font-semibold text-slate-900">
                {i + 1}. {s.title}
              </span>
              <span className="block text-xs leading-relaxed text-slate-500">{s.text}</span>
            </span>
          </li>
        ))}
      </ol>
    </Card>
  )
}
