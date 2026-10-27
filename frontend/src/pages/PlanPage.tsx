import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
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
    <div className="space-y-6">
      <div>
        <Link to={`/sessions/${sessionId}/analysis`} className="text-sm text-slate-500 hover:underline">
          ← Analysis
        </Link>
        <h1 className="mt-1 text-2xl font-semibold">Interview plan</h1>
        <p className="text-sm text-slate-500">
          These are the topics, in order. The questions stay hidden so the interview feels real, and follow-ups may be added on the way.
        </p>
      </div>
      <Card>
        <ol className="divide-y divide-slate-100">
          {plan.topics.map((t) => (
            <li key={t.index} className="flex items-center gap-3 py-2.5">
              <span className="w-6 text-sm text-slate-400">{t.index + 1}</span>
              <span className="min-w-0 flex-1 truncate">{t.topic}</span>
              <Badge tone="info">{LABELS[t.category]}</Badge>
              <Badge>{t.difficulty}</Badge>
            </li>
          ))}
        </ol>
      </Card>
      <div className="flex items-center justify-between rounded-xl border border-slate-200 bg-white p-4">
        <p className="text-sm text-slate-600">
          Answer one question at a time. Scores are not shown during the interview. If you use a local model, close other heavy apps so it stays fast.
        </p>
        <Button onClick={() => navigate(`/sessions/${sessionId}/interview`)}>Start interview</Button>
      </div>
    </div>
  )
}
