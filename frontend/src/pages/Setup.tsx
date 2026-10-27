import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { Button } from '../components/ui/button'
import { Card } from '../components/ui/card'
import { Field, Input } from '../components/ui/field'
import { PageHeader } from '../components/ui/page'
import { Segmented } from '../components/ui/segmented'
import { api, type Difficulty, type InterviewType } from '../lib/api'

export function Setup() {
  const navigate = useNavigate()
  const [title, setTitle] = useState('')
  const [role, setRole] = useState('')
  const [type, setType] = useState<InterviewType>('mixed')
  const [difficulty, setDifficulty] = useState<Difficulty>('medium')
  const [count, setCount] = useState('10')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function submit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const s = await api.createSession({
        title: title.trim(),
        target_role: role.trim(),
        interview_type: type,
        difficulty,
        question_count: Number(count),
      })
      navigate(`/sessions/${s.id}/upload`)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not create session')
      setBusy(false)
    }
  }

  return (
    <div className="mx-auto max-w-2xl">
      <PageHeader title="New interview" subtitle="Tell us what you are practising for. Next you will upload your resume and the job description." back={{ to: '/', label: 'All interviews' }} />
      <Card className="p-8">
        <form onSubmit={submit} className="space-y-6">
          <div className="grid gap-5 sm:grid-cols-2">
            <Field label="Session name" hint="Just for you, so you can find it later.">
              <Input required maxLength={200} value={title} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. Backend role practice #1" />
            </Field>
            <Field label="Target role" hint="The job you are interviewing for.">
              <Input required maxLength={200} value={role} onChange={(e) => setRole(e.target.value)} placeholder="e.g. Senior Python Developer" />
            </Field>
          </div>
          <Segmented
            label="Interview type"
            value={type}
            onChange={setType}
            options={[
              { value: 'mixed', label: 'Mixed', hint: 'Technical plus behavioural' },
              { value: 'technical', label: 'Technical', hint: 'Skills and projects' },
              { value: 'behavioural', label: 'Behavioural', hint: 'Situations and teamwork' },
            ]}
          />
          <Segmented
            label="Difficulty"
            value={difficulty}
            onChange={setDifficulty}
            options={[
              { value: 'easy', label: 'Easy', hint: 'Basics and definitions' },
              { value: 'medium', label: 'Medium', hint: 'Applied, with trade-offs' },
              { value: 'hard', label: 'Hard', hint: 'Design and failure modes' },
            ]}
          />
          <Segmented
            label="Number of topics"
            value={count}
            onChange={setCount}
            options={[
              { value: '8', label: '8', hint: 'about 15 min' },
              { value: '10', label: '10', hint: 'about 20 min' },
              { value: '12', label: '12', hint: 'about 25 min' },
              { value: '15', label: '15', hint: 'about 35 min' },
              { value: '20', label: '20', hint: 'about 45 min' },
            ]}
          />
          {error && (
            <p role="alert" className="rounded-xl bg-red-50 px-3.5 py-2.5 text-sm text-red-700">
              {error}
            </p>
          )}
          <Button type="submit" size="lg" className="w-full sm:w-auto" disabled={busy || !title.trim() || !role.trim()}>
            {busy ? 'Creating…' : 'Continue to uploads'}
          </Button>
        </form>
      </Card>
    </div>
  )
}
