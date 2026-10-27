import { CalendarCheck, Flame, Gauge, MessageCircleMore, Plus, Trash2 } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { BadgesCard } from '../components/dashboard/BadgesCard'
import { GettingStarted } from '../components/dashboard/GettingStarted'
import { NextActionCard } from '../components/dashboard/NextActionCard'
import { StatCard } from '../components/dashboard/StatCard'
import { TipCard } from '../components/dashboard/TipCard'
import { TrendChart } from '../components/dashboard/TrendChart'
import { PracticeActions } from '../components/PracticeActions'
import { ScoreBars } from '../components/ScoreBars'
import { Badge, type Tone } from '../components/ui/badge'
import { Button, buttonClasses } from '../components/ui/button'
import { Card } from '../components/ui/card'
import { PageHeader } from '../components/ui/page'
import { api, type Dashboard, type Session } from '../lib/api'
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

const dash = (n: number | null) => (n === null ? '—' : n)

export function Home() {
  const { user } = useAuth()
  const [sessions, setSessions] = useState<Session[] | null>(null)
  const [data, setData] = useState<Dashboard | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      const [list, d] = await Promise.all([api.listSessions(), api.dashboard()])
      setSessions(list)
      setData(d)
      setError(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load your interviews')
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

  const stats = data?.stats
  const latest = data?.trend[data.trend.length - 1]
  const weak = (data?.weakest ?? []).filter((t) => t.score < 60).map((t) => t.name).slice(0, 3)

  return (
    <div className="space-y-8">
      <PageHeader
        title={user ? `Hi ${user.name.split(' ')[0]}, ready to practise?` : 'Your interviews'}
        subtitle="Your progress, what to work on next, and all your interviews in one place."
        actions={
          <Link to="/new" className={buttonClasses('primary', 'md')}>
            <Plus className="size-4" aria-hidden /> New interview
          </Link>
        }
      />

      {error && (
        <p role="alert" className="rounded-xl bg-red-50 p-3.5 text-sm text-red-700">
          {error}
        </p>
      )}
      {!data && !error && <p className="text-slate-500">Loading…</p>}

      {data && stats && (
        <>
          <NextActionCard action={data.next_action} />

          <section aria-label="Your numbers" className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            <StatCard label="Latest score" value={dash(stats.latest_score)} change={stats.change} hint={stats.change === null ? 'out of 100' : 'vs your previous'} icon={<Gauge className="size-5" aria-hidden />} />
            <StatCard label="Average score" value={dash(stats.avg_score)} hint={stats.reports ? `across ${stats.reports} report${stats.reports === 1 ? '' : 's'}` : 'after your first report'} icon={<CalendarCheck className="size-5" aria-hidden />} />
            <StatCard label="Practice streak" value={`${stats.streak_days} ${stats.streak_days === 1 ? 'day' : 'days'}`} hint={`${stats.practice_days_30} practice day${stats.practice_days_30 === 1 ? '' : 's'} in 30 days`} icon={<Flame className="size-5" aria-hidden />} />
            <StatCard label="Answers given" value={stats.answers} hint={`${stats.finished} interview${stats.finished === 1 ? '' : 's'} finished`} icon={<MessageCircleMore className="size-5" aria-hidden />} />
          </section>

          {stats.reports === 0 ? (
            <GettingStarted />
          ) : (
            <div className="grid gap-6 lg:grid-cols-5">
              <Card className="flex flex-col lg:col-span-3">
                <TrendChart points={data.trend.map((t) => ({ id: t.session_id, label: t.title, date: t.date, score: t.score }))} />
              </Card>
              <Card className="space-y-4 lg:col-span-2">
                <ScoreBars title="Topics to work on" bars={data.weakest.map((t) => ({ label: t.name, value: t.score, detail: `${t.attempts} answer round${t.attempts === 1 ? '' : 's'}` }))} />
                {data.strongest.length > 0 && (
                  <p className="text-xs text-slate-500">
                    Strongest: <span className="font-medium text-slate-700">{data.strongest.map((t) => `${t.name} (${t.score})`).join(', ')}</span>
                  </p>
                )}
                {latest && <PracticeActions sessionId={latest.session_id} weak={weak} compact />}
              </Card>
            </div>
          )}

          <div className="grid gap-6 lg:grid-cols-2">
            {data.dimensions.length > 0 ? (
              <Card>
                <ScoreBars
                  title="How you answer (latest report)"
                  bars={data.dimensions.map((d) => ({ label: d.label, value: d.score, detail: d.change === null ? undefined : d.change === 0 ? 'no change vs previous' : `${d.change > 0 ? '▲ +' : '▼ '}${d.change} vs previous` }))}
                />
              </Card>
            ) : (
              <TipCard />
            )}
            <BadgesCard badges={data.badges} />
          </div>
          {data.dimensions.length > 0 && <TipCard />}
        </>
      )}

      <section aria-labelledby="all-interviews" className="space-y-3">
        <h2 id="all-interviews" className="text-lg font-semibold text-slate-900">
          All interviews
        </h2>
        {sessions?.length === 0 && <p className="rounded-2xl border border-dashed border-slate-300 bg-white/60 p-6 text-center text-sm text-slate-500">No interviews yet. Your first one will appear here.</p>}
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
                    {s.focus_topics && s.focus_topics.length > 0 && <Badge tone="brand">Focus: {s.focus_topics.join(', ')}</Badge>}
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
      </section>
    </div>
  )
}
