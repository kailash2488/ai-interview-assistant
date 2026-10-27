import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { DocumentSlot } from '../components/DocumentSlot'
import { Badge } from '../components/ui/badge'
import { PageHeader } from '../components/ui/page'
import { Stepper } from '../components/Stepper'
import { Button } from '../components/ui/button'
import { api, ApiError, type DocumentItem, type Session } from '../lib/api'

const POLL_MS = 1000
const isPending = (d: DocumentItem) => d.status === 'uploaded' || d.status === 'parsing'

export function Upload() {
  const { sessionId = '' } = useParams()
  const navigate = useNavigate()
  const [starting, setStarting] = useState(false)
  const [session, setSession] = useState<Session | null>(null)
  const [docs, setDocs] = useState<DocumentItem[]>([])
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    try {
      setDocs(await api.listDocuments(sessionId))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load documents')
    }
  }, [sessionId])

  useEffect(() => {
    api
      .getSession(sessionId)
      .then(setSession)
      .catch((e) => setError(e instanceof ApiError && e.status === 404 ? 'Session not found' : e.message))
    void refresh()
  }, [sessionId, refresh])

  const anyPending = docs.some(isPending)
  useEffect(() => {
    if (!anyPending) return
    const t = setInterval(() => void refresh(), POLL_MS)
    return () => clearInterval(t)
  }, [anyPending, refresh])

  if (error && !session) {
    return (
      <div className="space-y-4">
        <p role="alert" className="text-red-700">
          {error}
        </p>
        <Link to="/" className="text-brand-600 underline">
          Back to home
        </Link>
      </div>
    )
  }

  async function startAnalysis() {
    setStarting(true)
    try {
      const existing = await api.getAnalysis(sessionId)
      if (!existing || existing.status === 'failed') await api.analyze(sessionId)
      navigate(`/sessions/${sessionId}/analysis`)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not start analysis')
      setStarting(false)
    }
  }

  const byKind = (kind: DocumentItem['kind']) => docs.filter((d) => d.kind === kind)
  const ready = (kind: DocumentItem['kind']) => byKind(kind).some((d) => d.status === 'ready')
  const canContinue = ready('resume') && ready('jd')
  const common = { sessionId, onChanged: () => void refresh() }

  return (
    <div className="space-y-6">
      <Stepper sessionId={sessionId} current="documents" />
      <PageHeader
        title={session?.title ?? 'Loading…'}
        back={{ to: '/', label: 'All interviews' }}
        subtitle={
          session && (
            <span className="flex flex-wrap items-center gap-2">
              <span>{session.target_role}</span>
              <Badge>{session.interview_type}</Badge>
              <Badge>{session.difficulty}</Badge>
              <Badge>{session.question_count} questions</Badge>
            </span>
          )
        }
      />

      {error && session && (
        <p role="alert" className="rounded-md bg-red-50 p-3 text-sm text-red-700">
          {error}
        </p>
      )}

      <DocumentSlot {...common} kind="resume" title="Resume" required description="The candidate's resume." documents={byKind('resume')} />
      <DocumentSlot
        {...common}
        kind="jd"
        title="Job description"
        required
        allowPaste
        description="Upload the JD or paste its text."
        documents={byKind('jd')}
      />
      <DocumentSlot
        {...common}
        kind="other"
        title="Extra documents"
        multiple
        description="Optional: project descriptions, company notes, past feedback."
        documents={byKind('other')}
      />

      <div className="sticky bottom-4 z-10 flex items-center justify-between gap-4 rounded-2xl border border-slate-200/80 bg-white/90 p-4 shadow-lift backdrop-blur">
        <p className="text-sm text-slate-600">
          {canContinue
            ? 'Both required documents are ready.'
            : 'Upload a resume and a job description and wait for both to show Ready.'}
        </p>
        <Button disabled={!canContinue || starting} onClick={startAnalysis}>
          {starting ? 'Starting…' : 'Analyse documents'}
        </Button>
      </div>
    </div>
  )
}
