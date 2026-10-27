import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { QuestionCard, DIMENSION_LABELS } from '../components/QuestionCard'
import { Stepper } from '../components/Stepper'
import { ScoreBars } from '../components/ScoreBars'
import { Button } from '../components/ui/button'
import { Card } from '../components/ui/card'
import { api, reportPdfUrl, type Report } from '../lib/api'

const POLL_MS = 2000

export function ReportPage() {
  const { sessionId = '' } = useParams()
  const [report, setReport] = useState<Report | null | undefined>(undefined)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      setReport(await api.getReport(sessionId))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load the report')
    }
  }, [sessionId])

  useEffect(() => {
    void load()
  }, [load])

  const running = report?.status === 'running'
  useEffect(() => {
    if (!running) return
    const t = setInterval(() => void load(), POLL_MS)
    return () => clearInterval(t)
  }, [running, load])

  async function generate() {
    setError(null)
    try {
      setReport(await api.generateReport(sessionId))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not start the report')
    }
  }

  const back = (
    <Link to="/" className="text-sm text-slate-500 hover:underline">
      ← All interviews
    </Link>
  )

  if (report === undefined && !error) return <p className="text-slate-500">Loading…</p>

  const errorBox = error && (
    <p role="alert" className="rounded-md bg-red-50 p-3 text-sm text-red-700">
      {error}
    </p>
  )

  if (report === null || report === undefined) {
    return (
      <div className="space-y-4">
        {back}
        <Card className="space-y-3">
          <h1 className="text-xl font-semibold">Feedback report</h1>
          <p className="text-sm text-slate-600">
            Scores each of your answers against a rubric, then summarises your strengths, weak spots and a two-week study plan. With a local model this can
            take a few minutes; with Gemini it takes seconds.
          </p>
          <Button onClick={generate}>Generate feedback report</Button>
          {errorBox}
        </Card>
      </div>
    )
  }

  if (report.status === 'running') {
    return (
      <div className="space-y-4">
        {back}
        <Card role="status" className="space-y-2">
          <p className="font-medium">Evaluating your answers…</p>
          <p className="text-sm text-slate-500">
            {report.progress_total > 0 ? `${report.progress_done} of ${report.progress_total} answers evaluated.` : 'Starting…'} You can leave this page open.
          </p>
          <progress className="h-2 w-full" value={report.progress_done} max={Math.max(report.progress_total, 1)} aria-label="Evaluation progress" />
        </Card>
        {errorBox}
      </div>
    )
  }

  if (report.status === 'failed' || !report.report) {
    return (
      <div className="space-y-4">
        {back}
        <Card className="space-y-3 border-red-200">
          <p role="alert" className="text-red-700">
            The report failed: {report.error}
          </p>
          <p className="text-xs text-slate-500">Answers that were already evaluated are kept, so trying again is faster.</p>
          <Button onClick={generate}>Try again</Button>
        </Card>
        {errorBox}
      </div>
    )
  }

  const r = report.report
  const areas = [...r.areas].sort((a, b) => b.score_percent - a.score_percent)
  const dims = Object.entries(r.dimension_scores).sort((a, b) => b[1] - a[1])

  return (
    <div className="space-y-6">
      <Stepper sessionId={sessionId} current="report" />
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          {back}
          <h1 className="mt-2 text-3xl font-semibold tracking-tight text-slate-900">Feedback report</h1>
          <p className="mt-1 text-sm text-slate-500">{r.target_role}</p>
        </div>
        <div className="flex gap-2">
          <a href={reportPdfUrl(sessionId)} download>
            <Button variant="secondary" type="button">
              Download PDF
            </Button>
          </a>
          <Button
            variant="secondary"
            onClick={() => {
              if (window.confirm('Generate the report again? The current one will be replaced.')) void generate()
            }}
          >
            Regenerate
          </Button>
        </div>
      </div>
      {errorBox}
      {report.warnings.map((w) => (
        <p key={w} className="rounded-md bg-amber-50 p-3 text-sm text-amber-800">
          {w}
        </p>
      ))}

      <Card className="flex flex-col gap-6 border-brand-100 bg-gradient-to-br from-white via-white to-brand-50/70 p-7 sm:flex-row sm:items-center">
        <div className="text-center sm:w-48" aria-label={`Overall score ${r.overall_score} out of 100`}>
          <div className="text-gradient text-7xl font-semibold tabular-nums leading-none">{r.overall_score}</div>
          <div className="mt-1 text-sm text-slate-500">out of 100</div>
          <div aria-hidden className="mx-auto mt-3 h-1.5 w-32 overflow-hidden rounded-full bg-slate-200">
            <div className="h-full rounded-full bg-gradient-to-r from-brand-500 to-fuchsia-500" style={{ width: `${Math.max(0, Math.min(100, r.overall_score))}%` }} />
          </div>
        </div>
        <div className="space-y-2">
          <p className="text-xl font-semibold text-slate-900">{r.verdict}</p>
          <p className="text-sm text-slate-600">{r.summary}</p>
          <p className="text-xs text-slate-400">
            {r.verdict_basis} {r.coverage.evaluated} of {r.coverage.planned_topics} planned topics were scored
            {r.coverage.unanswered > 0 ? `; ${r.coverage.unanswered} question${r.coverage.unanswered === 1 ? ' was' : 's were'} left unanswered` : ''}.
          </p>
        </div>
      </Card>

      <div className="grid gap-6 md:grid-cols-2">
        <Card>
          <ScoreBars
            title="Score by topic"
            bars={areas.map((a) => ({ label: a.name, value: a.score_percent, detail: `${a.answers} answer${a.answers === 1 ? '' : 's'}` }))}
          />
        </Card>
        <Card>
          <ScoreBars title="Score by rubric dimension" bars={dims.map(([k, v]) => ({ label: DIMENSION_LABELS[k] ?? k, value: v }))} />
        </Card>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        <Card className="space-y-3">
          <h2 className="text-lg font-semibold">Top strengths</h2>
          {r.strengths.length === 0 && (
            <p className="text-sm text-slate-500">No topic scored high enough to count as a strength yet. The areas to improve are the place to start.</p>
          )}
          <ol className="space-y-3">
            {r.strengths.map((s) => (
              <li key={s.title}>
                <p className="font-medium text-slate-900">{s.title}</p>
                <p className="text-sm text-slate-600">{s.detail}</p>
              </li>
            ))}
          </ol>
        </Card>
        <Card className="space-y-3">
          <h2 className="text-lg font-semibold">Top areas to improve</h2>
          <ol className="space-y-3">
            {r.improvements.map((s) => (
              <li key={s.title}>
                <p className="font-medium text-slate-900">{s.title}</p>
                <p className="text-sm text-slate-600">{s.detail}</p>
              </li>
            ))}
          </ol>
        </Card>
      </div>

      <section className="space-y-3">
        <h2 className="text-lg font-semibold">Question by question</h2>
        <ul className="space-y-2">
          {r.questions.map((q) => (
            <QuestionCard key={q.order_no} q={q} />
          ))}
        </ul>
      </section>

      <Card className="space-y-3">
        <h2 className="text-lg font-semibold">How you communicated</h2>
        <ul className="list-inside list-disc space-y-1 text-sm text-slate-700">
          {r.communication.observations.map((o) => (
            <li key={o}>{o}</li>
          ))}
        </ul>
        <p className="text-xs text-slate-400">
          {r.communication.answers} answers · average {r.communication.avg_words} words (shortest {r.communication.shortest_words}, longest{' '}
          {r.communication.longest_words})
          {r.communication.avg_seconds !== null && ` · about ${r.communication.avg_seconds}s per answer`}
        </p>
      </Card>

      <Card className="space-y-4">
        <h2 className="text-lg font-semibold">Your improvement plan</h2>
        {r.improvement_plan.map((step) => (
          <div key={step.timeframe}>
            <p className="font-medium text-slate-900">
              {step.timeframe}: {step.focus}
            </p>
            <ul className="mt-1 list-inside list-disc text-sm text-slate-700">
              {step.actions.map((a) => (
                <li key={a}>{a}</li>
              ))}
            </ul>
          </div>
        ))}
      </Card>
      <p className="text-xs text-slate-400">Scored by {report.model}. Scores come from a rubric, so use them to compare your own attempts over time.</p>
    </div>
  )
}
