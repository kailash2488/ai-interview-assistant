import { CheckCircle2, Eye, EyeOff } from 'lucide-react'
import { useEffect, useState, type FormEvent } from 'react'
import { Link, Navigate, useNavigate, useSearchParams } from 'react-router-dom'
import { Logo } from '../components/Logo'
import { Button } from '../components/ui/button'
import { Field, Input } from '../components/ui/field'
import { api, ApiError } from '../lib/api'
import { useAuth } from '../lib/auth'

const EMAIL = /^[^@\s]{1,64}@[^@\s]+\.[^@\s]{2,}$/

const BENEFITS = [
  'Questions written from your own resume and the job description',
  'Follow-ups that dig into your answers, like a real interviewer',
  'A scored report with evidence quotes and a two-week study plan',
  'Your choice of AI: private on your computer, or fast in the cloud',
]

function PasswordInput({ value, onChange, autoComplete, id }: { value: string; onChange: (v: string) => void; autoComplete: string; id?: string }) {
  const [shown, setShown] = useState(false)
  return (
    <div className="relative">
      <Input id={id} type={shown ? 'text' : 'password'} value={value} onChange={(e) => onChange(e.target.value)} autoComplete={autoComplete} required className="pr-11" />
      <button
        type="button"
        onClick={() => setShown((s) => !s)}
        aria-label={shown ? 'Hide password' : 'Show password'}
        className="absolute inset-y-0 right-0 flex w-11 items-center justify-center text-slate-400 hover:text-slate-600"
      >
        {shown ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
      </button>
    </div>
  )
}

export function AuthPage({ mode }: { mode: 'login' | 'signup' }) {
  const { user, loading, login, signup } = useAuth()
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const next = params.get('next')
  const destination = next && next.startsWith('/') && !next.startsWith('//') ? next : '/'
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({})
  const [signupOpen, setSignupOpen] = useState(true)

  useEffect(() => {
    if (mode === 'signup') api.authConfig().then((c) => setSignupOpen(c.allow_signup)).catch(() => undefined)
  }, [mode])

  if (!loading && user) return <Navigate to={destination} replace />

  const isSignup = mode === 'signup'

  async function submit(e: FormEvent) {
    e.preventDefault()
    const errors: Record<string, string> = {}
    if (isSignup && !name.trim()) errors.name = 'Enter your name'
    if (!EMAIL.test(email.trim())) errors.email = 'Enter a valid email address'
    if (isSignup && password.length < 8) errors.password = 'Use at least 8 characters'
    if (!isSignup && !password) errors.password = 'Enter your password'
    setFieldErrors(errors)
    setError(null)
    if (Object.keys(errors).length) return
    setBusy(true)
    try {
      if (isSignup) await signup({ email: email.trim(), name: name.trim(), password })
      else await login({ email: email.trim(), password })
      navigate(destination, { replace: true })
    } catch (err) {
      setError(err instanceof ApiError || err instanceof Error ? err.message : 'Something went wrong')
      setBusy(false)
    }
  }

  return (
    <div className="grid min-h-screen lg:grid-cols-[minmax(0,1fr)_minmax(0,1.05fr)]">
      <div className="flex flex-col px-6 py-8 sm:px-12">
        <Logo />
        <div className="mx-auto flex w-full max-w-sm flex-1 flex-col justify-center py-10">
          <h1 className="text-3xl font-semibold tracking-tight text-slate-900">{isSignup ? 'Create your account' : 'Welcome back'}</h1>
          <p className="mt-2 text-sm text-slate-500">
            {isSignup ? 'Practice interviews that adapt to your resume and the role you want.' : 'Log in to continue your interview practice.'}
          </p>

          {isSignup && !signupOpen ? (
            <div role="alert" className="mt-8 rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
              Sign-ups are closed on this server. Ask the owner for an account, or{' '}
              <Link to="/login" className="font-medium underline">
                log in
              </Link>
              .
            </div>
          ) : (
            <form onSubmit={submit} className="mt-8 space-y-4" noValidate>
              {isSignup && (
                <Field label="Name" error={fieldErrors.name}>
                  <Input value={name} onChange={(e) => setName(e.target.value)} autoComplete="name" required maxLength={100} />
                </Field>
              )}
              <Field label="Email" error={fieldErrors.email}>
                <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" required />
              </Field>
              <Field label="Password" hint={isSignup ? 'At least 8 characters.' : undefined} error={fieldErrors.password}>
                <PasswordInput value={password} onChange={setPassword} autoComplete={isSignup ? 'new-password' : 'current-password'} />
              </Field>
              {error && (
                <p role="alert" className="rounded-xl bg-red-50 px-3.5 py-2.5 text-sm text-red-700">
                  {error}
                  {isSignup && error.includes('already exists') && (
                    <>
                      {' '}
                      <Link to="/login" className="font-medium underline">
                        Log in
                      </Link>
                    </>
                  )}
                </p>
              )}
              <Button type="submit" size="lg" className="w-full" disabled={busy}>
                {busy ? (isSignup ? 'Creating account…' : 'Logging in…') : isSignup ? 'Create account' : 'Log in'}
              </Button>
            </form>
          )}

          <p className="mt-6 text-center text-sm text-slate-500">
            {isSignup ? (
              <>
                Already have an account?{' '}
                <Link to={next ? `/login?next=${encodeURIComponent(next)}` : '/login'} className="font-medium text-brand-700 hover:underline">
                  Log in
                </Link>
              </>
            ) : (
              <>
                New here?{' '}
                <Link to={next ? `/signup?next=${encodeURIComponent(next)}` : '/signup'} className="font-medium text-brand-700 hover:underline">
                  Create an account
                </Link>
              </>
            )}
          </p>
        </div>
        <p className="text-center text-xs text-slate-400">
          <Link to="/" className="hover:text-slate-600">
            ← Back to home
          </Link>
        </p>
      </div>

      <aside className="relative hidden overflow-hidden bg-gradient-to-br from-brand-700 via-brand-600 to-fuchsia-600 p-12 text-white lg:flex lg:flex-col lg:justify-center">
        <div aria-hidden className="absolute -right-24 -top-24 size-96 rounded-full bg-white/10 blur-3xl" />
        <div aria-hidden className="absolute -bottom-32 -left-16 size-96 rounded-full bg-fuchsia-300/20 blur-3xl" />
        <div className="relative max-w-md">
          <p className="text-sm font-medium uppercase tracking-widest text-brand-200">Interview practice that adapts</p>
          <h2 className="mt-4 text-4xl font-semibold leading-tight tracking-tight">Walk into your next interview having already had it.</h2>
          <ul className="mt-10 space-y-4">
            {BENEFITS.map((b) => (
              <li key={b} className="flex gap-3 text-brand-50">
                <CheckCircle2 className="mt-0.5 size-5 shrink-0 text-white" aria-hidden />
                <span>{b}</span>
              </li>
            ))}
          </ul>
          <p className="mt-12 text-sm text-brand-200">Open source and free to run. Your documents stay in your own database.</p>
        </div>
      </aside>
    </div>
  )
}
