import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../lib/api'
import { useAuth } from '../lib/auth'
import { Avatar } from './UserMenu'
import { Button } from './ui/button'
import { Card } from './ui/card'
import { Field, Input } from './ui/field'

export function AccountCard() {
  const { user, forget } = useAuth()
  const navigate = useNavigate()
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [pwBusy, setPwBusy] = useState(false)
  const [pwError, setPwError] = useState<string | null>(null)
  const [pwDone, setPwDone] = useState(false)
  const [deletePw, setDeletePw] = useState('')
  const [delError, setDelError] = useState<string | null>(null)

  if (!user) return null

  async function changePassword(e: FormEvent) {
    e.preventDefault()
    setPwError(null)
    setPwDone(false)
    if (next.length < 8) {
      setPwError('Use at least 8 characters for the new password')
      return
    }
    setPwBusy(true)
    try {
      await api.changePassword({ current_password: current, new_password: next })
      setCurrent('')
      setNext('')
      setPwDone(true)
    } catch (err) {
      setPwError(err instanceof Error ? err.message : 'Could not change the password')
    } finally {
      setPwBusy(false)
    }
  }

  async function deleteAccount() {
    setDelError(null)
    if (!window.confirm('Delete your account and every interview, document and report in it? This cannot be undone.')) return
    try {
      await api.deleteAccount(deletePw)
      forget()
      navigate('/')
    } catch (err) {
      setDelError(err instanceof Error ? err.message : 'Could not delete the account')
    }
  }

  return (
    <Card className="space-y-6">
      <div className="flex items-center gap-4">
        <Avatar name={user.name} className="size-12 text-lg" />
        <div className="min-w-0">
          <h2 className="truncate text-lg font-semibold text-slate-900">{user.name}</h2>
          <p className="truncate text-sm text-slate-500">{user.email}</p>
        </div>
      </div>

      <form onSubmit={changePassword} className="space-y-4 border-t border-slate-100 pt-6">
        <h3 className="text-sm font-semibold text-slate-900">Change password</h3>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Current password">
            <Input type="password" autoComplete="current-password" value={current} onChange={(e) => setCurrent(e.target.value)} required />
          </Field>
          <Field label="New password" hint="At least 8 characters.">
            <Input type="password" autoComplete="new-password" value={next} onChange={(e) => setNext(e.target.value)} required />
          </Field>
        </div>
        {pwError && (
          <p role="alert" className="text-sm text-red-700">
            {pwError}
          </p>
        )}
        {pwDone && (
          <p role="status" className="text-sm text-emerald-700">
            Password changed. Your other devices were signed out.
          </p>
        )}
        <Button type="submit" variant="secondary" disabled={pwBusy || !current || !next}>
          {pwBusy ? 'Saving…' : 'Change password'}
        </Button>
      </form>

      <div className="space-y-3 border-t border-slate-100 pt-6">
        <h3 className="text-sm font-semibold text-red-700">Delete account</h3>
        <p className="text-sm text-slate-500">Removes your account, interviews, documents, reports and saved API key from this server.</p>
        <Field label="Your password" error={delError}>
          <Input type="password" autoComplete="current-password" value={deletePw} onChange={(e) => setDeletePw(e.target.value)} />
        </Field>
        <Button type="button" variant="danger" disabled={!deletePw} onClick={deleteAccount} className="border border-red-200 disabled:border-slate-200 disabled:text-slate-400">
          Delete my account
        </Button>
      </div>
    </Card>
  )
}
