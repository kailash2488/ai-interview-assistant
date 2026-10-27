import { RotateCcw, Target } from 'lucide-react'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../lib/api'
import { Button } from './ui/button'

/** "Practise again" without uploading or analysing anything twice. Starts a copy of an interview and goes to its plan. */
export function PracticeActions({ sessionId, weak, compact = false }: { sessionId: string; weak: string[]; compact?: boolean }) {
  const navigate = useNavigate()
  const [busy, setBusy] = useState<'same' | 'weak' | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function go(focus: 'same' | 'weak') {
    setBusy(focus)
    setError(null)
    try {
      // the weak spots on screen are exactly the topics the new interview focuses on
      const next = await api.retry(sessionId, focus, focus === 'weak' ? weak : undefined)
      await api.createPlan(next.id)
      navigate(`/sessions/${next.id}/plan`)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not start the new interview')
      setBusy(null)
    }
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-2">
        <Button variant={compact ? 'secondary' : 'primary'} onClick={() => go('weak')} disabled={busy !== null || weak.length === 0} title={weak.length === 0 ? 'Every topic scored 60 or more' : undefined}>
          <Target className="size-4" aria-hidden /> {busy === 'weak' ? 'Preparing…' : 'Practise my weak spots'}
        </Button>
        <Button variant="secondary" onClick={() => go('same')} disabled={busy !== null}>
          <RotateCcw className="size-4" aria-hidden /> {busy === 'same' ? 'Preparing…' : 'Try the same interview again'}
        </Button>
      </div>
      {weak.length > 0 && <p className="text-xs text-slate-500">Weak spots to focus on: {weak.join(', ')}.</p>}
      {error && (
        <p role="alert" className="text-sm text-red-700">
          {error}
        </p>
      )}
    </div>
  )
}
