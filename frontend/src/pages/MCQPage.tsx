import { useEffect, useState } from 'react'
import { CheckCircle2, Circle, LoaderCircle, RotateCcw, Trophy, XCircle } from 'lucide-react'
import { Link, useParams } from 'react-router-dom'
import { Badge } from '../components/ui/badge'
import { Button } from '../components/ui/button'
import { Card } from '../components/ui/card'
import { api, type MCQState } from '../lib/api'

const LETTERS = ['A', 'B', 'C', 'D']
const pendingStarts = new Map<string, Promise<MCQState>>()

function startOnce(sessionId: string) {
  const existing = pendingStarts.get(sessionId)
  if (existing) return existing
  const request = api.startMCQ(sessionId).finally(() => pendingStarts.delete(sessionId))
  pendingStarts.set(sessionId, request)
  return request
}

export function MCQPage() {
  const { sessionId = '' } = useParams()
  const [state, setState] = useState<MCQState | null>(null)
  const [selected, setSelected] = useState<number | null>(null)
  const [busy, setBusy] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api.getMCQ(sessionId).then(async (s) => setState(s.current || s.status === 'completed' ? s : await startOnce(sessionId)))
      .catch((e) => setError(e instanceof Error ? e.message : 'Could not start the quiz')).finally(() => setBusy(false))
  }, [sessionId])

  async function submit() {
    if (selected === null) return
    setBusy(true); setError(null)
    try { setState(await api.answerMCQ(sessionId, state!.current!.question_id, selected)); setSelected(null) }
    catch (e) { setError(e instanceof Error ? e.message : 'Could not save your answer') }
    finally { setBusy(false) }
  }

  if (busy && !state) return <div className="flex min-h-80 items-center justify-center gap-3 text-slate-500"><LoaderCircle className="size-5 animate-spin" /> Preparing your complete quiz from the interview plan…</div>
  if (error && !state) return <p role="alert" className="rounded-xl bg-red-50 p-4 text-red-700">{error}</p>
  if (!state) return null
  const complete = state.status === 'completed'
  const pct = state.total ? Math.round(100 * state.answered / state.total) : 0

  if (complete) return <div className="space-y-6">
    <Card className="overflow-hidden border-0 bg-gradient-to-br from-brand-700 via-brand-600 to-fuchsia-600 p-8 text-center text-white shadow-lift">
      <Trophy className="mx-auto size-12" /><p className="mt-3 text-sm font-semibold uppercase tracking-[.18em] text-indigo-100">Quiz complete</p><h1 className="mt-2 text-5xl font-semibold">{state.score}%</h1><p className="mt-2 text-indigo-100">{state.results.filter((q) => q.correct).length} of {state.total} correct</p>
    </Card>
    <div className="space-y-4">{state.results.map((q) => <Card key={q.question_id} className={q.correct ? 'border-emerald-200' : 'border-red-200'}>
      <div className="flex items-start gap-3">{q.correct ? <CheckCircle2 className="mt-0.5 size-5 shrink-0 text-emerald-600" /> : <XCircle className="mt-0.5 size-5 shrink-0 text-red-600" />}<div className="min-w-0 flex-1"><div className="flex flex-wrap gap-2"><Badge>{q.topic}</Badge><Badge tone={q.correct ? 'success' : 'danger'}>{q.correct ? 'Correct' : 'Review'}</Badge></div><h2 className="mt-3 font-semibold text-slate-900">{q.order_no}. {q.text}</h2><p className="mt-2 text-sm text-slate-600">Your answer: <strong>{LETTERS[q.selected_index ?? 0]}. {q.options[q.selected_index ?? 0]}</strong></p>{!q.correct && q.correct_index !== null && <p className="mt-1 text-sm text-emerald-700">Correct answer: <strong>{LETTERS[q.correct_index]}. {q.options[q.correct_index]}</strong></p>}<p className="mt-3 rounded-xl bg-slate-50 p-3 text-sm leading-6 text-slate-600">{q.explanation}</p></div></div>
    </Card>)}</div>
    <div className="flex flex-wrap gap-3"><Link to="/new"><Button><RotateCcw className="size-4" /> New practice</Button></Link><Link to="/" className="self-center text-sm font-medium text-brand-700 hover:underline">Back to dashboard</Link></div>
  </div>

  const q = state.current!
  return <div className="mx-auto max-w-4xl space-y-6">
    <div className="flex items-end justify-between gap-4"><div><p className="text-xs font-semibold uppercase tracking-[.18em] text-brand-600">MCQ practice</p><h1 className="mt-1 text-3xl font-semibold">Question {state.answered + 1} of {state.total}</h1></div><span className="text-sm font-medium text-slate-500">{pct}% complete</span></div>
    <div className="h-2 overflow-hidden rounded-full bg-slate-200"><div className="h-full rounded-full bg-gradient-to-r from-brand-500 to-fuchsia-500 transition-all" style={{ width: `${pct}%` }} /></div>
    <Card className="p-6 sm:p-8"><Badge tone="brand">{q.topic}</Badge><h2 className="mt-4 text-xl font-semibold leading-8 text-slate-900">{q.text}</h2><div className="mt-6 grid gap-3">{q.options.map((option, i) => <button key={i} type="button" onClick={() => setSelected(i)} disabled={busy} className={`flex items-start gap-4 rounded-2xl border p-4 text-left transition-all ${selected === i ? 'border-brand-500 bg-brand-50 ring-4 ring-brand-500/10' : 'border-slate-200 bg-white hover:border-brand-300 hover:bg-slate-50'}`}><span className={`flex size-8 shrink-0 items-center justify-center rounded-full text-sm font-semibold ${selected === i ? 'bg-brand-600 text-white' : 'bg-slate-100 text-slate-600'}`}>{LETTERS[i]}</span><span className="pt-1 text-sm leading-6 text-slate-700">{option}</span><Circle className={`ml-auto mt-1 size-5 shrink-0 ${selected === i ? 'fill-brand-600 text-brand-600' : 'text-slate-300'}`} /></button>)}</div></Card>
    {error && <p role="alert" className="rounded-xl bg-red-50 p-3 text-sm text-red-700">{error}</p>}
    <div className="flex items-center justify-between"><p className="text-xs text-slate-500">Answers and explanations are revealed after the final question.</p><Button size="lg" onClick={submit} disabled={selected === null || busy}>{busy ? <><LoaderCircle className="size-4 animate-spin" /> Saving answer…</> : 'Lock answer & continue'}</Button></div>
  </div>
}
