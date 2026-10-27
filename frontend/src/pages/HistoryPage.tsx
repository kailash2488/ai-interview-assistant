import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { ScoreBars } from '../components/ScoreBars'
import { Button } from '../components/ui/button'
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

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Your progress</h1>
        <p className="text-sm text-slate-500">Interviews with a finished report, oldest first. Compare two attempts to see what improved.</p>
      </div>
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
          <Card>
            <ScoreBars
              title="Overall score by attempt"
              bars={list.map((i) => ({ label: i.title, value: i.overall_score, detail: `${formatDate(i.created_at)} · ${i.target_role}` }))}
            />
          </Card>

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
