import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { Stepper } from '../components/Stepper'
import { PageHeader } from '../components/ui/page'
import { Badge } from '../components/ui/badge'
import { Button } from '../components/ui/button'
import { Card } from '../components/ui/card'
import { Lightbulb, Mic, Target } from 'lucide-react'
import { api, type Category, type Plan, type Session } from '../lib/api'

const LABELS: Record<Category, string> = {
  intro: 'Introduction',
  core: 'Core skill',
  project: 'Project deep dive',
  gap: 'Gap area',
  behavioural: 'Behavioural',
  closing: 'Your questions',
}

export function PlanPage() {
  const { sessionId = '' } = useParams()
  const navigate = useNavigate()
  const [plan, setPlan] = useState<Plan | null | undefined>(undefined)
  const [error, setError] = useState<string | null>(null)
  const [session, setSession] = useState<Session | null>(null)

  useEffect(() => {
    api.getSession(sessionId).then(setSession).catch(() => undefined)
    api.getPlan(sessionId).then(setPlan).catch((e) => setError(e instanceof Error ? e.message : 'Failed to load plan'))
  }, [sessionId])

  if (error) return <p role="alert" className="text-red-700">{error}</p>
  if (plan === undefined) return <p className="text-slate-500">Loading…</p>
  if (plan === null) {
    return (
      <div className="space-y-3">
        <p>There is no interview plan yet.</p>
        <Link to={`/sessions/${sessionId}/analysis`} className="text-brand-600 underline">
          Go to the analysis
        </Link>
      </div>
    )
  }

  return (
    <div>
      <Stepper sessionId={sessionId} current="plan" />
      <PageHeader
        title="Interview plan"
        back={{ to: `/sessions/${sessionId}/analysis`, label: 'Analysis' }}
        subtitle={session?.practice_mode === 'mcq' ? 'These topics will become multiple-choice questions. Correct answers stay hidden until the quiz is complete.' : 'These are the topics, in order. The questions stay hidden so the interview feels real, and follow-ups may be added on the way.'}
      />
      {session?.focus_topics && session.focus_topics.length > 0 && (
        <div className="mb-4 flex items-start gap-3 rounded-2xl border border-brand-200 bg-brand-50 p-4 text-sm text-brand-900">
          <Target className="mt-0.5 size-5 shrink-0 text-brand-600" aria-hidden />
          <p>
            <strong className="font-semibold">Practising your weak spots.</strong> These topics come first: {session.focus_topics.join(', ')}.
          </p>
        </div>
      )}
      <Card className="p-2 sm:p-3">
        <ol>
          {plan.topics.map((t) => (
            <li key={t.index} className="flex items-center gap-4 rounded-xl px-4 py-3 transition-colors hover:bg-slate-50">
              <span className="flex size-8 shrink-0 items-center justify-center rounded-full bg-brand-50 text-sm font-semibold text-brand-700">{t.index + 1}</span>
              <span className="min-w-0 flex-1 truncate font-medium text-slate-900">{t.topic}</span>
              <Badge tone="brand">{LABELS[t.category]}</Badge>
              <Badge>{t.difficulty}</Badge>
            </li>
          ))}
        </ol>
      </Card>
      <section aria-label="Before you start" className="mt-6 grid gap-4 sm:grid-cols-3">
        {[
          { icon: Lightbulb, title: 'Point first', text: 'Start with your answer in one sentence, then give an example.' },
          { icon: Lightbulb, title: 'One to two minutes', text: 'Most answers fit in 60 to 120 seconds, with one real example and a number.' },
          session?.practice_mode === 'mcq'
            ? { icon: Target, title: 'Choose one answer', text: 'Each question has four choices and exactly one correct answer.' }
            : { icon: Mic, title: 'Prefer to talk?', text: 'Switch on voice mode in the interview. Use headphones in a quiet room.' },
        ].map((t) => (
          <div key={t.title} className="flex items-start gap-3 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
            <span className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-amber-50 text-amber-700">
              <t.icon className="size-4" aria-hidden />
            </span>
            <span>
              <span className="block text-sm font-semibold text-slate-900">{t.title}</span>
              <span className="block text-xs leading-relaxed text-slate-500">{t.text}</span>
            </span>
          </div>
        ))}
      </section>
      <div className="mt-6 flex flex-wrap items-center justify-between gap-4 rounded-2xl border border-brand-200 bg-gradient-to-r from-brand-50 to-fuchsia-50 p-5">
        <p className="max-w-xl text-sm text-slate-600">
          {session?.practice_mode === 'mcq' ? 'Choose one option per question. Your score, correct answers and explanations appear after the final question.' : 'Answer one question at a time. Scores are not shown during the interview. If you use a local model, close other heavy apps so it stays fast.'}
        </p>
        <Button size="lg" onClick={() => navigate(`/sessions/${sessionId}/${session?.practice_mode === 'mcq' ? 'mcq' : 'interview'}`)}>
          {session?.practice_mode === 'mcq' ? 'Start MCQ quiz' : 'Start interview'}
        </Button>
      </div>
    </div>
  )
}
