import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { LogoMark } from '../components/Logo'
import { Stepper } from '../components/Stepper'
import { Button } from '../components/ui/button'
import { Card } from '../components/ui/card'
import { Textarea } from '../components/ui/field'
import { api, wsUrl, type ServerMessage, type Turn } from '../lib/api'

type Phase = 'connecting' | 'thinking' | 'waiting' | 'complete' | 'error' | 'disconnected'

const MAX_ANSWER = 5000

export function Interview() {
  const { sessionId = '' } = useParams()
  const navigate = useNavigate()
  const [reportError, setReportError] = useState<string | null>(null)
  const [starting, setStarting] = useState(false)
  const socketRef = useRef<WebSocket | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)
  const [turns, setTurns] = useState<Turn[]>([])
  const [streaming, setStreaming] = useState('')
  const [phase, setPhase] = useState<Phase>('connecting')
  const [progress, setProgress] = useState({ asked: 0, total: 0 })
  const [error, setError] = useState<{ message: string; retryable: boolean } | null>(null)
  const [draft, setDraft] = useState('')
  const [elapsed, setElapsed] = useState(0)

  const send = useCallback((payload: object) => socketRef.current?.send(JSON.stringify(payload)), [])

  const connect = useCallback(() => {
    socketRef.current?.close()
    setPhase('connecting')
    setError(null)
    const ws = new WebSocket(wsUrl(`/sessions/${sessionId}/interview`))
    socketRef.current = ws
    ws.onmessage = (ev) => {
      const msg = JSON.parse(ev.data) as ServerMessage
      switch (msg.type) {
        case 'state':
          setTurns(msg.turns)
          setProgress({ asked: msg.main_asked, total: msg.main_total })
          if (msg.status === 'completed') setPhase('complete')
          else ws.send(JSON.stringify({ type: 'start' })) // starts, or resumes after a reload
          break
        case 'thinking':
          setPhase('thinking')
          setStreaming('')
          break
        case 'token':
          setStreaming((s) => s + msg.text)
          break
        case 'question':
          setStreaming('')
          setProgress({ asked: msg.progress.main_asked, total: msg.progress.main_total })
          setTurns((prev) => {
            const turn: Turn = {
              question_id: msg.question_id, order_no: msg.order_no, topic: msg.topic, ack: msg.ack,
              text: msg.text, is_follow_up: msg.is_follow_up, answer: null,
            }
            return prev.some((t) => t.question_id === turn.question_id)
              ? prev.map((t) => (t.question_id === turn.question_id ? { ...t, ...turn, answer: t.answer } : t))
              : [...prev, turn]
          })
          setElapsed(0)
          setPhase('waiting')
          break
        case 'complete':
          setStreaming('')
          setPhase('complete')
          break
        case 'error':
          setStreaming('')
          setError({ message: msg.message, retryable: msg.retryable })
          setPhase('error')
          break
      }
    }
    ws.onclose = () => {
      if (socketRef.current === ws) setPhase((p) => (p === 'complete' ? p : 'disconnected'))
    }
  }, [sessionId])

  useEffect(() => {
    connect()
    return () => {
      const ws = socketRef.current
      socketRef.current = null
      ws?.close()
    }
  }, [connect])

  useEffect(() => {
    if (phase !== 'waiting') return
    const t = setInterval(() => setElapsed((s) => s + 1), 1000)
    return () => clearInterval(t)
  }, [phase])

  useEffect(() => {
    bottomRef.current?.scrollIntoView?.({ behavior: 'smooth' })
  }, [turns, streaming, phase])

  function submit() {
    const text = draft.trim()
    if (!text || phase !== 'waiting') return
    setTurns((prev) => prev.map((t, i) => (i === prev.length - 1 ? { ...t, answer: text } : t)))
    setDraft('')
    setPhase('thinking')
    send({ type: 'answer', text })
  }

  function endInterview() {
    if (window.confirm('End the interview now? Unanswered questions will be skipped.')) send({ type: 'end' })
  }

  async function startReport() {
    setStarting(true)
    setReportError(null)
    try {
      // If a report already exists, just open it; generating is always the user's choice.
      if (!(await api.getReport(sessionId))) await api.generateReport(sessionId)
      navigate(`/sessions/${sessionId}/report`)
    } catch (e) {
      setReportError(e instanceof Error ? e.message : 'Could not start the report')
      setStarting(false)
    }
  }

  const canAnswer = phase === 'waiting'
  const mmss = `${Math.floor(elapsed / 60)}:${String(elapsed % 60).padStart(2, '0')}`

  const pct = progress.total > 0 ? Math.min(100, Math.round((Math.min(progress.asked, progress.total) / progress.total) * 100)) : 0

  return (
    <div className="space-y-5">
      <Stepper sessionId={sessionId} current="interview" />
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight text-slate-900">Interview</h1>
          {progress.total > 0 && (
            <div className="mt-2 flex items-center gap-3">
              <span aria-label="progress" className="text-sm text-slate-600">
                Question {Math.min(progress.asked, progress.total)} of {progress.total}
              </span>
              <span aria-hidden className="h-1.5 w-40 overflow-hidden rounded-full bg-slate-200">
                <span className="block h-full rounded-full bg-gradient-to-r from-brand-500 to-fuchsia-500 transition-all duration-500" style={{ width: `${pct}%` }} />
              </span>
            </div>
          )}
        </div>
        <div className="flex items-center gap-3 text-sm text-slate-600">
          {canAnswer && <span className="tabular-nums text-slate-400">{mmss}</span>}
          {phase !== 'complete' && (
            <Button variant="secondary" onClick={endInterview} disabled={phase === 'connecting' || phase === 'disconnected'}>
              End interview
            </Button>
          )}
        </div>
      </div>

      <Card className="space-y-5 bg-gradient-to-b from-white to-slate-50/60 p-5 sm:p-7" aria-live="polite">
        {turns.map((t) => (
          <div key={t.question_id} className="space-y-3">
            <div className="flex items-start gap-3">
              <LogoMark className="mt-0.5 size-8 shrink-0" />
              <div className="max-w-[85%] rounded-2xl rounded-tl-sm border border-slate-200 bg-white px-4 py-3 text-sm leading-relaxed text-slate-800 shadow-sm">
                {t.ack && <p className="mb-1 text-slate-400">{t.ack}</p>}
                <p>{t.text}</p>
              </div>
            </div>
            {t.answer && (
              <div className="flex justify-end">
                <div className="max-w-[85%] whitespace-pre-wrap rounded-2xl rounded-tr-sm bg-gradient-to-br from-brand-500 to-brand-700 px-4 py-3 text-sm leading-relaxed text-white shadow-sm">
                  {t.answer}
                </div>
              </div>
            )}
          </div>
        ))}
        {phase === 'thinking' && (
          <div className="flex items-start gap-3">
            <LogoMark className="mt-0.5 size-8 shrink-0" />
            <div className="max-w-[85%] rounded-2xl rounded-tl-sm border border-slate-200 bg-white px-4 py-3 text-sm text-slate-500 shadow-sm" role="status">
              {streaming || 'The interviewer is thinking…'}
            </div>
          </div>
        )}
        {phase === 'connecting' && <p className="text-sm text-slate-500">Connecting…</p>}
        <div ref={bottomRef} />
      </Card>

      {phase === 'error' && error && (
        <div role="alert" className="flex items-center justify-between gap-3 rounded-xl bg-red-50 p-3.5 text-sm text-red-700">
          <span>{error.message}</span>
          {error.retryable && (
            <Button variant="secondary" onClick={() => send({ type: 'start' })}>
              Try again
            </Button>
          )}
        </div>
      )}

      {phase === 'disconnected' && (
        <div role="alert" className="flex items-center justify-between gap-3 rounded-xl bg-amber-50 p-3.5 text-sm text-amber-800">
          <span>Connection lost. Your answers so far are saved.</span>
          <Button variant="secondary" onClick={connect}>
            Reconnect
          </Button>
        </div>
      )}

      {phase === 'complete' ? (
        <Card className="space-y-3 border-brand-200 bg-gradient-to-br from-brand-50 to-white">
          <p className="text-xl font-semibold text-slate-900">Interview complete.</p>
          <p className="text-sm text-slate-600">When you are ready, generate your feedback report. Nothing is scored until you ask.</p>
          {reportError && (
            <p role="alert" className="text-sm text-red-700">
              {reportError}
            </p>
          )}
          <div className="flex flex-wrap items-center gap-4 pt-1">
            <Button size="lg" onClick={startReport} disabled={starting}>
              {starting ? 'Starting…' : 'Generate feedback report'}
            </Button>
            <Link to="/" className="text-sm font-medium text-brand-700 hover:underline">
              Back to your interviews
            </Link>
          </div>
        </Card>
      ) : (
        <Card className="space-y-3 p-4 sm:p-5">
          <Textarea
            rows={4}
            value={draft}
            maxLength={MAX_ANSWER}
            disabled={!canAnswer}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
                e.preventDefault()
                submit()
              }
            }}
            placeholder={canAnswer ? 'Type your answer… (Ctrl+Enter to send)' : 'Wait for the next question…'}
            aria-label="Your answer"
            className="resize-none border-0 bg-transparent p-1 shadow-none focus:ring-0"
          />
          <div className="flex items-center justify-between border-t border-slate-100 pt-3">
            <span className="text-xs text-slate-400">
              {draft.length}/{MAX_ANSWER}
            </span>
            <Button onClick={submit} disabled={!canAnswer || !draft.trim()}>
              Send answer
            </Button>
          </div>
        </Card>
      )}
    </div>
  )
}
