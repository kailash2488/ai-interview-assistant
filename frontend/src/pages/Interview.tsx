import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { Button } from '../components/ui/button'
import { Card } from '../components/ui/card'
import { Textarea } from '../components/ui/field'
import { wsUrl, type ServerMessage, type Turn } from '../lib/api'

type Phase = 'connecting' | 'thinking' | 'waiting' | 'complete' | 'error' | 'disconnected'

const MAX_ANSWER = 5000

export function Interview() {
  const { sessionId = '' } = useParams()
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

  const canAnswer = phase === 'waiting'
  const mmss = `${Math.floor(elapsed / 60)}:${String(elapsed % 60).padStart(2, '0')}`

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <Link to="/" className="text-sm text-slate-500 hover:underline">
            ← All interviews
          </Link>
          <h1 className="text-2xl font-semibold">Interview</h1>
        </div>
        <div className="flex items-center gap-3 text-sm text-slate-600">
          {progress.total > 0 && (
            <span aria-label="progress">
              Question {Math.min(progress.asked, progress.total)} of {progress.total}
            </span>
          )}
          {canAnswer && <span className="tabular-nums text-slate-400">{mmss}</span>}
          {phase !== 'complete' && (
            <Button variant="secondary" onClick={endInterview} disabled={phase === 'connecting' || phase === 'disconnected'}>
              End interview
            </Button>
          )}
        </div>
      </div>

      <Card className="space-y-4" aria-live="polite">
        {turns.map((t) => (
          <div key={t.question_id} className="space-y-2">
            <div className="max-w-[85%] rounded-2xl rounded-tl-sm bg-slate-100 px-4 py-2.5 text-sm">
              {t.ack && <p className="mb-1 text-slate-500">{t.ack}</p>}
              <p>{t.text}</p>
            </div>
            {t.answer && (
              <div className="ml-auto max-w-[85%] whitespace-pre-wrap rounded-2xl rounded-tr-sm bg-brand-600 px-4 py-2.5 text-sm text-white">
                {t.answer}
              </div>
            )}
          </div>
        ))}
        {phase === 'thinking' && (
          <div className="max-w-[85%] rounded-2xl rounded-tl-sm bg-slate-100 px-4 py-2.5 text-sm text-slate-600" role="status">
            {streaming || 'The interviewer is thinking…'}
          </div>
        )}
        {phase === 'connecting' && <p className="text-sm text-slate-500">Connecting…</p>}
        <div ref={bottomRef} />
      </Card>

      {phase === 'error' && error && (
        <div role="alert" className="flex items-center justify-between gap-3 rounded-md bg-red-50 p-3 text-sm text-red-700">
          <span>{error.message}</span>
          {error.retryable && (
            <Button variant="secondary" onClick={() => send({ type: 'start' })}>
              Try again
            </Button>
          )}
        </div>
      )}

      {phase === 'disconnected' && (
        <div role="alert" className="flex items-center justify-between gap-3 rounded-md bg-amber-50 p-3 text-sm text-amber-800">
          <span>Connection lost. Your answers so far are saved.</span>
          <Button variant="secondary" onClick={connect}>
            Reconnect
          </Button>
        </div>
      )}

      {phase === 'complete' ? (
        <Card className="space-y-2">
          <p className="font-medium">Interview complete.</p>
          <p className="text-sm text-slate-500">Your feedback report arrives with Phase 4.</p>
          <Link to="/" className="text-sm text-brand-600 underline">
            Back to your interviews
          </Link>
        </Card>
      ) : (
        <div className="space-y-2">
          <Textarea
            rows={5}
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
          />
          <div className="flex items-center justify-between">
            <span className="text-xs text-slate-400">
              {draft.length}/{MAX_ANSWER}
            </span>
            <Button onClick={submit} disabled={!canAnswer || !draft.trim()}>
              Send answer
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}
