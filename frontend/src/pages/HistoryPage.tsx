import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { ArrowRight, Award, BarChart3, CalendarDays, Target, TrendingDown, TrendingUp } from 'lucide-react'
import { ScoreBars } from '../components/ScoreBars'
import { Button } from '../components/ui/button'
import { PageHeader } from '../components/ui/page'
import { Card } from '../components/ui/card'
import { Field, Select } from '../components/ui/field'
import { api, type Comparison, type DeltaRow, type HistoryItem } from '../lib/api'
import { formatDate } from '../lib/utils'

/** Plus/minus sign and an arrow, never colour alone. */
function Delta({ value }: { value: number | null }) {
  if (value === null) return <span className="text-slate-400">n/a</span>
  if (value === 0) return <span className="text-slate-500">no change</span>
  return value > 0 ? (
    <span className="font-medium text-emerald-700">▲ +{value}</span>
  ) : (
    <span className="font-medium text-red-700">▼ {value}</span>
  )
}

function DeltaTable({ title, rows }: { title: string; rows: DeltaRow[] }) {
  return (
    <Card className="space-y-2">
      <h2 className="text-base font-semibold">{title}</h2>
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-xs text-slate-500">
            <th className="py-1 font-medium">&nbsp;</th>
            <th className="py-1 font-medium">Before</th>
            <th className="py-1 font-medium">After</th>
            <th className="py-1 font-medium">Change</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.name} className="border-t border-slate-100">
              <td className="py-1.5 text-slate-800">{r.name}</td>
              <td className="py-1.5 tabular-nums">{r.a ?? '–'}</td>
              <td className="py-1.5 tabular-nums">{r.b ?? '–'}</td>
              <td className="py-1.5 tabular-nums">
                <Delta value={r.delta} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  )
}

export function HistoryPage() {
  const [params, setParams] = useSearchParams()
  const [items, setItems] = useState<HistoryItem[] | null>(null)
  const [comparison, setComparison] = useState<Comparison | null>(null)
  const [error, setError] = useState<string | null>(null)
  const a = params.get('a') ?? ''
  const b = params.get('b') ?? ''

  useEffect(() => {
    api.getHistory().then(setItems).catch((e) => setError(e instanceof Error ? e.message : 'Failed to load history'))
  }, [])

  useEffect(() => {
    if (!a || !b) return
    let cancelled = false
    api
      .compare(a, b)
      .then((c) => {
        if (!cancelled) {
          setComparison(c)
          setError(null)
        }
      })
      .catch((e) => {
        if (!cancelled) {
          setComparison(null)
          setError(e instanceof Error ? e.message : 'Could not compare')
        }
      })
    return () => {
      cancelled = true
    }
  }, [a, b])

  if (!items && !error) return <p className="text-slate-500">Loading…</p>
  const list = items ?? []
  const shown = a && b ? comparison : null
  const latest = list.at(-1)
  const first = list[0]
  const best = list.length ? Math.max(...list.map((item) => item.overall_score)) : 0
  const average = list.length ? Math.round(list.reduce((sum, item) => sum + item.overall_score, 0) / list.length) : 0
  const improvement = latest && first && list.length > 1 ? latest.overall_score - first.overall_score : null

  return (
    <div className="space-y-6">
      <PageHeader title="Your progress" subtitle="Turn every completed interview into a clearer next step." actions={<Link to="/new"><Button>New practice <ArrowRight className="size-4" /></Button></Link>} />
      {error && (
        <p role="alert" className="rounded-md bg-red-50 p-3 text-sm text-red-700">
          {error}
        </p>
      )}

      {list.length === 0 && !error && (
        <Card className="space-y-2 text-center text-slate-500">
          <p>No finished reports yet.</p>
          <Link to="/" className="text-brand-600 underline">
            Go to your interviews
          </Link>
        </Card>
      )}

      {list.length > 0 && (
        <>
          <section aria-label="Performance summary" className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            {[
              { label: 'Latest score', value: `${latest!.overall_score}`, note: latest!.title, icon: Target, tone: 'from-brand-500 to-indigo-600' },
              { label: 'Personal best', value: `${best}`, note: 'Highest report score', icon: Award, tone: 'from-amber-400 to-orange-500' },
              { label: 'Average score', value: `${average}`, note: `Across ${list.length} attempt${list.length === 1 ? '' : 's'}`, icon: BarChart3, tone: 'from-cyan-500 to-blue-600' },
              { label: 'Overall growth', value: improvement === null ? '—' : `${improvement >= 0 ? '+' : ''}${improvement}`, note: improvement === null ? 'Complete another attempt' : 'First report to latest', icon: improvement !== null && improvement < 0 ? TrendingDown : TrendingUp, tone: improvement !== null && improvement < 0 ? 'from-rose-500 to-red-600' : 'from-emerald-500 to-teal-600' },
            ].map(({ label, value, note, icon: Icon, tone }) => <Card key={label} className="relative overflow-hidden p-5"><div aria-hidden className={`absolute -right-8 -top-8 size-24 rounded-full bg-gradient-to-br ${tone} opacity-10`} /><div className="flex items-start justify-between"><div><p className="text-xs font-semibold uppercase tracking-[.14em] text-slate-500">{label}</p><p className="mt-2 text-3xl font-semibold tabular-nums text-slate-900">{value}<span className="text-base font-medium text-slate-400">{value === '—' ? '' : '/100'}</span></p></div><span className={`flex size-10 items-center justify-center rounded-xl bg-gradient-to-br text-white ${tone}`}><Icon className="size-5" /></span></div><p className="mt-3 truncate text-xs text-slate-500" title={note}>{note}</p></Card>)}
          </section>

          <Card className="overflow-hidden border-0 bg-gradient-to-r from-slate-950 via-indigo-950 to-brand-800 text-white shadow-lift">
            <div className="flex flex-col justify-between gap-5 sm:flex-row sm:items-center"><div><p className="text-xs font-semibold uppercase tracking-[.16em] text-indigo-200">Performance insight</p><h2 className="mt-2 text-xl font-semibold">{improvement === null ? 'Your baseline is ready' : improvement > 0 ? `You have improved ${improvement} points` : improvement === 0 ? 'Your score is holding steady' : 'Use the next attempt to rebuild momentum'}</h2><p className="mt-2 max-w-2xl text-sm leading-6 text-indigo-100">{improvement === null ? 'Complete one more interview for a meaningful side-by-side comparison.' : improvement >= 0 ? 'Compare attempts below to identify which rubric dimensions and topics created the change.' : 'A lower score is useful evidence—not a setback. Compare topics, practise the weakest area, and try again.'}</p></div><Link to="/new" className="shrink-0 rounded-xl bg-white px-4 py-2.5 text-center text-sm font-semibold text-brand-700 shadow-sm hover:bg-indigo-50">Start focused practice</Link></div>
          </Card>

          <Card className="p-5 sm:p-6">
            <ScoreBars
              title="Overall score by attempt"
              bars={list.map((i) => ({ label: i.title, value: i.overall_score, detail: `${formatDate(i.created_at)} · ${i.target_role}` }))}
            />
          </Card>

          <Card className="space-y-4"><div className="flex items-center justify-between"><div><h2 className="text-base font-semibold">Recent reports</h2><p className="mt-1 text-sm text-slate-500">Open a report to review feedback and stronger sample answers.</p></div><CalendarDays className="size-5 text-brand-600" /></div><div className="divide-y divide-slate-100">{[...list].reverse().slice(0, 5).map((item) => <Link key={item.session_id} to={`/sessions/${item.session_id}/report`} className="flex items-center gap-4 py-3 first:pt-0 last:pb-0 hover:text-brand-700"><span className="flex size-11 shrink-0 items-center justify-center rounded-xl bg-brand-50 font-semibold tabular-nums text-brand-700">{item.overall_score}</span><span className="min-w-0 flex-1"><span className="block truncate text-sm font-medium text-slate-800">{item.title}</span><span className="block truncate text-xs text-slate-500">{item.target_role} · {formatDate(item.created_at)} · {item.verdict}</span></span><ArrowRight className="size-4 shrink-0 text-slate-400" /></Link>)}</div></Card>

          <Card className="space-y-4">
            <h2 className="text-base font-semibold">Compare two attempts</h2>
            {list.length < 2 ? (
              <p className="text-sm text-slate-500">Finish and score a second interview to compare.</p>
            ) : (
              <div className="grid items-end gap-4 sm:grid-cols-[1fr_1fr_auto]">
                <Field label="Earlier attempt">
                  <Select value={a} onChange={(e) => setParams({ a: e.target.value, ...(b ? { b } : {}) })}>
                    <option value="">Choose…</option>
                    {list.map((i) => (
                      <option key={i.session_id} value={i.session_id}>
                        {i.title} ({i.overall_score})
                      </option>
                    ))}
                  </Select>
                </Field>
                <Field label="Later attempt">
                  <Select value={b} onChange={(e) => setParams({ ...(a ? { a } : {}), b: e.target.value })}>
                    <option value="">Choose…</option>
                    {list.map((i) => (
                      <option key={i.session_id} value={i.session_id}>
                        {i.title} ({i.overall_score})
                      </option>
                    ))}
                  </Select>
                </Field>
                <Button variant="ghost" onClick={() => setParams({})} disabled={!a && !b}>
                  Clear
                </Button>
              </div>
            )}
          </Card>
        </>
      )}

      {shown && (
        <div className="space-y-6">
          <Card className="flex flex-wrap items-center gap-6">
            <div>
              <p className="text-xs uppercase tracking-wide text-slate-500">Overall score</p>
              <p className="text-3xl font-semibold tabular-nums">
                {shown.a.overall_score} → {shown.b.overall_score}
              </p>
            </div>
            <p className="text-xl">
              <Delta value={shown.overall_delta} />
            </p>
            <p className="text-sm text-slate-500">
              “{shown.a.title}” vs “{shown.b.title}”
              {!shown.same_role && ' · these interviews were for different roles, so compare with care'}
            </p>
          </Card>
          <div className="grid gap-6 md:grid-cols-2">
            <DeltaTable title="By rubric dimension" rows={shown.dimensions} />
            <DeltaTable title="By topic" rows={shown.areas} />
          </div>
          <p className="text-xs text-slate-400">
            Topics that appear in only one attempt show “–” and no change. Average answer length: {shown.a.avg_words} → {shown.b.avg_words} words.
          </p>
        </div>
      )}
    </div>
  )
}
