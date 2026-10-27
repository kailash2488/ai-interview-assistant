import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { ChipList } from '../components/ChipList'
import { Stepper } from '../components/Stepper'
import { PageHeader } from '../components/ui/page'
import { Badge } from '../components/ui/badge'
import { Button } from '../components/ui/button'
import { Card } from '../components/ui/card'
import { api, ApiError, type Analysis as AnalysisData, type CandidateProfile, type JDRequirements } from '../lib/api'

const POLL_MS = 2000

export function Analysis() {
  const { sessionId = '' } = useParams()
  const navigate = useNavigate()
  const [analysis, setAnalysis] = useState<AnalysisData | null | undefined>(undefined)
  const [profile, setProfile] = useState<CandidateProfile | null>(null)
  const [reqs, setReqs] = useState<JDRequirements | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  const adopt = useCallback((a: AnalysisData | null) => {
    setAnalysis(a)
    setProfile(a?.profile ?? null)
    setReqs(a?.requirements ?? null)
  }, [])

  const load = useCallback(async () => {
    try {
      adopt(await api.getAnalysis(sessionId))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load analysis')
    }
  }, [sessionId, adopt])

  useEffect(() => {
    void load()
  }, [load])

  const running = analysis?.status === 'running'
  useEffect(() => {
    if (!running) return
    const t = setInterval(() => void load(), POLL_MS)
    return () => clearInterval(t)
  }, [running, load])

  async function rerun() {
    setError(null)
    try {
      adopt(await api.analyze(sessionId))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not start analysis')
    }
  }

  async function buildPlan() {
    setError(null)
    try {
      await api.createPlan(sessionId)
      navigate(`/sessions/${sessionId}/plan`)
    } catch (e) {
      if (e instanceof ApiError && e.status === 409 && (await api.getPlan(sessionId))) {
        navigate(`/sessions/${sessionId}/plan`) // interview already started: the plan is fixed
      } else {
        setError(e instanceof Error ? e.message : 'Could not build the plan')
      }
    }
  }

  const dirty =
    analysis?.status === 'ready' &&
    (JSON.stringify(profile) !== JSON.stringify(analysis.profile) || JSON.stringify(reqs) !== JSON.stringify(analysis.requirements))

  async function save() {
    if (!profile || !reqs) return
    setSaving(true)
    setError(null)
    try {
      adopt(await api.patchAnalysis(sessionId, { profile, requirements: reqs }))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not save changes')
    } finally {
      setSaving(false)
    }
  }

  const back = (
    <Link to={`/sessions/${sessionId}/upload`} className="text-sm text-slate-500 hover:underline">
      ← Documents
    </Link>
  )

  if (analysis === undefined && !error) return <p className="text-slate-500">Loading…</p>

  if (analysis === null) {
    return (
      <div className="space-y-4">
        {back}
        <Card className="space-y-3">
          <p>No analysis yet.</p>
          <Button onClick={rerun}>Analyse documents</Button>
          {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
        </Card>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <Stepper sessionId={sessionId} current="analysis" />
      <PageHeader title="Analysis review" back={{ to: `/sessions/${sessionId}/upload`, label: 'Documents' }} subtitle="Check what was extracted and fix mistakes before the interview plan is built." />

      {error && <p role="alert" className="rounded-md bg-red-50 p-3 text-sm text-red-700">{error}</p>}

      {running && (
        <Card role="status" className="space-y-1">
          <p className="font-medium">Analysing your documents…</p>
          <p className="text-sm text-slate-500">
            A local model reads your resume and the job description. On a CPU this can take a few minutes. You can leave this page open.
          </p>
        </Card>
      )}

      {analysis?.status === 'failed' && (
        <Card className="space-y-3 border-red-200">
          <p role="alert" className="text-red-700">Analysis failed: {analysis.error}</p>
          <Button onClick={rerun}>Try again</Button>
        </Card>
      )}

      {analysis?.status === 'ready' && analysis.gap && profile && reqs && (
        <>
          {analysis.warnings.map((w) => (
            <p key={w} className="rounded-md bg-amber-50 p-3 text-sm text-amber-800">{w}</p>
          ))}

          <Card className="space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold">Match summary</h2>
              {analysis.gap.match_percent !== null && (
                <Badge tone={analysis.gap.match_percent >= 70 ? 'success' : 'info'}>
                  {analysis.gap.match_percent}% of must-haves matched
                </Badge>
              )}
            </div>
            <SummaryRow title="Matching skills" items={analysis.gap.matched_skills} tone="success" />
            <SummaryRow title="Gaps (JD wants, resume doesn't show)" items={analysis.gap.gaps} tone="danger" />
            <SummaryRow title="Nice-to-have matched" items={analysis.gap.nice_to_have_matched} tone="success" />
            <SummaryRow title="Nice-to-have missing" items={analysis.gap.nice_to_have_missing} tone="neutral" />
            <SummaryRow title="Strengths to warm up with" items={analysis.gap.strengths} tone="info" />
            {analysis.gap.claims_to_probe.length > 0 && (
              <div>
                <p className="text-sm font-medium text-slate-700">Claims the interviewer will probe</p>
                <ul className="mt-1 list-inside list-disc text-sm text-slate-600">
                  {analysis.gap.claims_to_probe.map((c) => (
                    <li key={c.text}>
                      {c.text} <span className="text-slate-400">— {c.reason}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </Card>

          <Card className="space-y-4">
            <h2 className="text-lg font-semibold">Candidate profile</h2>
            <p className="text-sm text-slate-600">
              {profile.name ?? 'Name not found'} · {profile.current_role ?? 'Role not found'}
              {profile.total_experience_years !== null && ` · ${profile.total_experience_years} yrs`}
            </p>
            <ChipList
              label="Skills"
              items={profile.skills.map((s) => s.name)}
              onChange={(names) =>
                setProfile({
                  ...profile,
                  skills: names.map((n) => profile.skills.find((s) => s.name === n) ?? { name: n, level: 'unknown', evidence: '' }),
                })
              }
            />
            {profile.projects.length > 0 && (
              <div className="text-sm text-slate-600">
                <p className="font-medium text-slate-700">Projects</p>
                <ul className="list-inside list-disc">
                  {profile.projects.map((p) => (
                    <li key={p.title}>
                      {p.title} <span className="text-slate-400">({p.tech_stack.join(', ')})</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </Card>

          <Card className="space-y-4">
            <h2 className="text-lg font-semibold">Job requirements</h2>
            <p className="text-sm text-slate-600">
              {reqs.role_title ?? 'Role not found'} · {reqs.seniority}
            </p>
            <ChipList label="Must-have skills" items={reqs.must_have_skills} onChange={(v) => setReqs({ ...reqs, must_have_skills: v })} />
            <ChipList label="Nice-to-have skills" tone="slate" items={reqs.nice_to_have_skills} onChange={(v) => setReqs({ ...reqs, nice_to_have_skills: v })} />
          </Card>

          <div className="flex items-center justify-between rounded-xl border border-slate-200 bg-white p-4">
            <div className="flex gap-2">
              <Button onClick={save} disabled={!dirty || saving}>
                {saving ? 'Saving…' : 'Save changes'}
              </Button>
              <Button variant="secondary" onClick={rerun}>
                Re-run analysis
              </Button>
            </div>
            <Button onClick={buildPlan} disabled={dirty || saving} title={dirty ? 'Save your changes first' : undefined}>
              Build interview plan
            </Button>
          </div>
          <p className="text-xs text-slate-400">
            Model: {analysis.model}
            {analysis.user_edited && ' · edited by you'}. Re-running discards your edits.
          </p>
        </>
      )}
    </div>
  )
}

function SummaryRow({ title, items, tone }: { title: string; items: string[]; tone: 'success' | 'danger' | 'info' | 'neutral' }) {
  return (
    <div className="space-y-1">
      <p className="text-sm font-medium text-slate-700">{title}</p>
      <div className="flex flex-wrap gap-1.5">
        {items.length === 0 ? <span className="text-sm text-slate-400">None</span> : items.map((i) => <Badge key={i} tone={tone}>{i}</Badge>)}
      </div>
    </div>
  )
}
