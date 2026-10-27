import { Plus, Trash2 } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Badge } from '../components/ui/badge'
import { Button } from '../components/ui/button'
import { Card } from '../components/ui/card'
import { api, type Session } from '../lib/api'
import { formatDate } from '../lib/utils'

export function Home() {
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
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Your interviews</h1>
        <Link to="/new">
          <Button>
            <Plus className="size-4" /> New interview
          </Button>
        </Link>
      </div>

      {error && (
        <p role="alert" className="rounded-md bg-red-50 p-3 text-sm text-red-700">
          {error}
        </p>
      )}
      {!sessions && !error && <p className="text-slate-500">Loading…</p>}
      {sessions?.length === 0 && (
        <Card className="text-center text-slate-500">No interviews yet. Start one with “New interview”.</Card>
      )}

      <ul className="space-y-3">
        {sessions?.map((s) => (
          <li key={s.id}>
            <Card className="flex items-center justify-between gap-4">
              <Link to={`/sessions/${s.id}/upload`} className="min-w-0 flex-1">
                <p className="truncate font-medium">{s.title}</p>
                <p className="truncate text-sm text-slate-500">
                  {s.target_role} · {formatDate(s.created_at)}
                </p>
              </Link>
              {(s.status === 'completed' || s.status === 'reported') && (
                <Link to={`/sessions/${s.id}/report`} className="text-sm text-brand-600 underline">
                  {s.status === 'reported' ? 'Report' : 'Get report'}
                </Link>
              )}
              <Badge>{s.interview_type}</Badge>
              {s.overall_score !== null ? <Badge tone={s.overall_score >= 70 ? 'success' : s.overall_score >= 45 ? 'info' : 'danger'}>Score {s.overall_score}</Badge> : <Badge>{s.question_count} questions</Badge>}
              <Button variant="danger" onClick={() => remove(s)} aria-label={`Delete ${s.title}`}>
                <Trash2 className="size-4" />
              </Button>
            </Card>
          </li>
        ))}
      </ul>
    </div>
  )
}
