import { ArrowRight, MessageSquareText, Plus, Trash2 } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Badge, type Tone } from '../components/ui/badge'
import { buttonClasses, Button } from '../components/ui/button'
import { Card } from '../components/ui/card'
import { PageHeader } from '../components/ui/page'
import { api, type Session } from '../lib/api'
import { useAuth } from '../lib/auth'
import { formatDate } from '../lib/utils'

const STAGES: Record<string, { label: string; tone: Tone; next: (id: string) => string }> = {
  created: { label: 'Draft', tone: 'neutral', next: (id) => `/sessions/${id}/upload` },
  analysed: { label: 'Analysed', tone: 'info', next: (id) => `/sessions/${id}/analysis` },
  planned: { label: 'Ready to start', tone: 'brand', next: (id) => `/sessions/${id}/plan` },
  in_progress: { label: 'In progress', tone: 'brand', next: (id) => `/sessions/${id}/interview` },
  completed: { label: 'Finished', tone: 'info', next: (id) => `/sessions/${id}/interview` },
  reported: { label: 'Scored', tone: 'success', next: (id) => `/sessions/${id}/report` },
}

function scoreTone(score: number): Tone {
  return score >= 70 ? 'success' : score >= 45 ? 'info' : 'danger'
}

export function Home() {
  const { user } = useAuth()
  const [sessions, setSessions] = useState<Session[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      setSessions(await api.listSessions())
      setError(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load sessions')
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  async function remove(s: Session) {
    if (!window.confirm(`Delete "${s.title}" and all its documents?`)) return
    try {
      await api.deleteSession(s.id)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Delete failed')
    }
    void load()
  }

  return (
    <div>
      <PageHeader
        title="Your interviews"
        subtitle={user ? `Welcome back, ${user.name.split(' ')[0]}. Pick up where you left off or start a new practice interview.` : undefined}
        actions={
          <Link to="/new" className={buttonClasses('primary', 'md')}>
            <Plus className="size-4" aria-hidden /> New interview
          </Link>
        }
      />

      {error && (
        <p role="alert" className="mb-4 rounded-xl bg-red-50 p-3.5 text-sm text-red-700">
          {error}
        </p>
      )}
      {!sessions && !error && <p className="text-slate-500">Loading…</p>}

      {sessions?.length === 0 && (
        <Card className="flex flex-col items-center px-6 py-16 text-center">
          <span className="flex size-14 items-center justify-center rounded-2xl bg-brand-50 text-brand-600">
            <MessageSquareText className="size-7" aria-hidden />
          </span>
          <h2 className="mt-5 text-xl font-semibold text-slate-900">No interviews yet</h2>
          <p className="mt-2 max-w-sm text-sm text-slate-500">Upload your resume and a job description and the assistant will run a mock interview just for you.</p>
          <Link to="/new" className={buttonClasses('primary', 'lg', 'mt-6')}>
            Start your first interview <ArrowRight className="size-4" aria-hidden />
          </Link>
        </Card>
      )}

      <ul className="space-y-3">
        {sessions?.map((s) => {
          const stage = STAGES[s.status] ?? STAGES.created
          return (
            <li key={s.id}>
              <Card className="flex items-center gap-4 p-5 transition-shadow hover:shadow-lift">
                <Link to={stage.next(s.id)} className="min-w-0 flex-1">
                  <p className="truncate text-base font-semibold text-slate-900">{s.title}</p>
                  <p className="mt-0.5 truncate text-sm text-slate-500">
                    {s.target_role} · {formatDate(s.created_at)}
                  </p>
                </Link>
                <div className="hidden items-center gap-2 sm:flex">
                  <Badge>{s.interview_type}</Badge>
                  <Badge>{s.question_count} topics</Badge>
                  {s.overall_score !== null ? <Badge tone={scoreTone(s.overall_score)}>Score {s.overall_score}</Badge> : <Badge tone={stage.tone}>{stage.label}</Badge>}
                </div>
                {(s.status === 'completed' || s.status === 'reported') && (
                  <Link to={`/sessions/${s.id}/report`} className="text-sm font-medium text-brand-700 hover:underline">
                    {s.status === 'reported' ? 'Report' : 'Get report'}
                  </Link>
                )}
                <Button variant="ghost" size="sm" onClick={() => remove(s)} aria-label={`Delete ${s.title}`} className="text-slate-400 hover:bg-red-50 hover:text-red-600">
                  <Trash2 className="size-4" />
                </Button>
              </Card>
            </li>
          )
        })}
      </ul>
    </div>
  )
}
