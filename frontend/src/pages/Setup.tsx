import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { Button } from '../components/ui/button'
import { Card } from '../components/ui/card'
import { Field, Input, Select } from '../components/ui/field'
import { api, type Difficulty, type InterviewType } from '../lib/api'

export function Setup() {
  const navigate = useNavigate()
  const [title, setTitle] = useState('')
  const [role, setRole] = useState('')
  const [type, setType] = useState<InterviewType>('mixed')
  const [difficulty, setDifficulty] = useState<Difficulty>('medium')
  const [count, setCount] = useState(10)
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
        question_count: count,
      })
      navigate(`/sessions/${s.id}/upload`)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not create session')
      setBusy(false)
    }
  }

  return (
    <div className="mx-auto max-w-xl space-y-6">
      <h1 className="text-2xl font-semibold">New interview</h1>
      <Card>
        <form onSubmit={submit} className="space-y-4">
          <Field label="Session name">
            <Input required maxLength={200} value={title} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. Backend role practice #1" />
          </Field>
          <Field label="Target role">
            <Input required maxLength={200} value={role} onChange={(e) => setRole(e.target.value)} placeholder="e.g. Senior Python Developer" />
          </Field>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <Field label="Interview type">
              <Select value={type} onChange={(e) => setType(e.target.value as InterviewType)}>
                <option value="mixed">Mixed</option>
                <option value="technical">Technical</option>
                <option value="behavioural">Behavioural</option>
              </Select>
            </Field>
            <Field label="Difficulty">
              <Select value={difficulty} onChange={(e) => setDifficulty(e.target.value as Difficulty)}>
                <option value="easy">Easy</option>
                <option value="medium">Medium</option>
                <option value="hard">Hard</option>
              </Select>
            </Field>
            <Field label="Questions">
              <Select value={count} onChange={(e) => setCount(Number(e.target.value))}>
                {[8, 10, 12, 15, 20].map((n) => (
                  <option key={n} value={n}>
                    {n}
                  </option>
                ))}
              </Select>
            </Field>
          </div>
          {error && (
            <p role="alert" className="text-sm text-red-700">
              {error}
            </p>
          )}
          <Button type="submit" disabled={busy || !title.trim() || !role.trim()}>
            {busy ? 'Creating…' : 'Continue to uploads'}
          </Button>
        </form>
      </Card>
    </div>
  )
}
