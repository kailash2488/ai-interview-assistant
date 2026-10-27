import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { Stepper } from '../components/Stepper'
import { PageHeader } from '../components/ui/page'
import { Badge } from '../components/ui/badge'
import { Button } from '../components/ui/button'
import { Card } from '../components/ui/card'
import { api, type Category, type Plan } from '../lib/api'

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

  useEffect(() => {
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
        subtitle="These are the topics, in order. The questions stay hidden so the interview feels real, and follow-ups may be added on the way."
      />
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
      <div className="mt-6 flex flex-wrap items-center justify-between gap-4 rounded-2xl border border-brand-200 bg-gradient-to-r from-brand-50 to-fuchsia-50 p-5">
        <p className="max-w-xl text-sm text-slate-600">
          Answer one question at a time. Scores are not shown during the interview. If you use a local model, close other heavy apps so it stays fast.
        </p>
        <Button size="lg" onClick={() => navigate(`/sessions/${sessionId}/interview`)}>
          Start interview
        </Button>
      </div>
    </div>
  )
}
