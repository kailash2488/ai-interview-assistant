import { useEffect, useState, type FormEvent } from 'react'
import { AccountCard } from '../components/AccountCard'
import { PageHeader } from '../components/ui/page'
import { useOptionalAuth } from '../lib/auth'
import { Button } from '../components/ui/button'
import { Card } from '../components/ui/card'
import { Field, Input, Select } from '../components/ui/field'
import { cn } from '../lib/utils'
import { api, type DataSummary, type LLMSettings, type LLMTestResult, type Provider } from '../lib/api'

const OPTIONS: Array<{ id: Provider; title: string; blurb: string }> = [
  {
    id: 'ollama',
    title: 'Local model (free)',
    blurb: 'Runs on this computer with Ollama. No account, no key, and your resume never leaves your machine. Slower on a laptop without a GPU.',
  },
  {
    id: 'gemini',
    title: 'Google Gemini (cloud)',
    blurb: 'Much faster. Needs your own API key. Your resume and job description are sent to Google.',
  },
]

export function SettingsPage() {
  const auth = useOptionalAuth()
  const [saved, setSaved] = useState<LLMSettings | null>(null)
  const [provider, setProvider] = useState<Provider>('ollama')
  const [model, setModel] = useState('gemini-3.5-flash-lite')
  const [key, setKey] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [test, setTest] = useState<LLMTestResult | null>(null)
  const [data, setData] = useState<DataSummary | null>(null)
  const [confirmText, setConfirmText] = useState('')
  const [dataNotice, setDataNotice] = useState<string | null>(null)

  function adopt(s: LLMSettings) {
    setSaved(s)
    setProvider(s.provider)
    setModel(s.gemini_model)
    setKey('')
  }

  useEffect(() => {
    api.getLLMSettings().then(adopt).catch((e) => setError(e instanceof Error ? e.message : 'Failed to load settings'))
    api.getDataSummary().then(setData).catch(() => undefined)
  }, [])

  async function wipe() {
    setError(null)
    try {
      setData(await api.deleteAllData())
      setConfirmText('')
      setDataNotice('All interviews, documents, answers and reports were deleted.')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not delete your data')
    }
  }

  async function save(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    setNotice(null)
    setTest(null)
    try {
      adopt(await api.saveLLMSettings({ provider, gemini_model: model, ...(key.trim() ? { gemini_api_key: key.trim() } : {}) }))
      setNotice('Saved. New analyses and interviews use this setting.')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not save')
    } finally {
      setBusy(false)
    }
  }

  async function runTest() {
    setBusy(true)
    setTest(null)
    setError(null)
    try {
      setTest(await api.testLLM())
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Test failed')
    } finally {
      setBusy(false)
    }
  }

  async function removeKey() {
    if (!window.confirm('Remove the saved Gemini key and switch back to the local model?')) return
    setError(null)
    setTest(null)
    try {
      adopt(await api.removeGeminiKey())
      setNotice('Key removed.')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not remove the key')
    }
  }

  if (!saved && !error) return <p className="text-slate-500">Loading…</p>

  const models = saved?.gemini_models ?? []
  const chosen = models.find((m) => m.id === model)
  const needsKey = provider === 'gemini' && !saved?.gemini_key_set && !key.trim()
  const dirty = saved !== null && (provider !== saved.provider || model !== saved.gemini_model || key.trim() !== '')

  return (
    <div className="mx-auto max-w-3xl space-y-8">
      <PageHeader title="Settings" subtitle="Your account, the AI model that runs your interviews, and your data." />

      {auth?.user && <AccountCard />}

      <section aria-labelledby="ai-model" className="space-y-4">
      <h2 id="ai-model" className="text-lg font-semibold text-slate-900">AI model</h2>
      <form onSubmit={save} className="space-y-4">
        <fieldset className="space-y-3">
          <legend className="sr-only">Model provider</legend>
          {OPTIONS.map((o) => (
            <label
              key={o.id}
              className={cn(
                'block cursor-pointer rounded-2xl border bg-white p-5 shadow-sm transition-all hover:border-slate-300',
                provider === o.id ? 'border-brand-500 ring-4 ring-brand-500/10' : 'border-slate-200',
              )}
            >
              <span className="flex items-center gap-3">
                <input type="radio" name="provider" value={o.id} checked={provider === o.id} onChange={() => setProvider(o.id)} className="accent-brand-600" />
                <span className="font-medium">{o.title}</span>
              </span>
              <span className="mt-1 block pl-7 text-sm text-slate-500">{o.blurb}</span>
            </label>
          ))}
        </fieldset>

        {provider === 'gemini' && (
          <Card className="space-y-4">
            <p className="text-sm text-slate-600">
              Create a key in{' '}
              <a href="https://aistudio.google.com/apikey" target="_blank" rel="noreferrer" className="text-brand-600 underline">
                Google AI Studio
              </a>
              . A key from a free project uses the free tier: limited requests per minute, and Google may use your prompts to improve its products.
              A key from a project with billing turned on uses the paid tier, with higher limits.
            </p>
            <Field
              label="Gemini API key"
              hint={
                saved?.gemini_key_set
                  ? `A key ending ${saved.gemini_key_hint ?? ''} is saved${saved.gemini_key_source === 'environment' ? ' (from the backend environment)' : ' on this computer'}. Leave blank to keep it.`
                  : 'Stored only on this computer, in the backend data folder. It is never shown again.'
              }
            >
              <Input
                type="password"
                autoComplete="off"
                spellCheck={false}
                value={key}
                onChange={(e) => setKey(e.target.value)}
                placeholder={saved?.gemini_key_set ? '••••••••••••' : 'Paste your key'}
              />
            </Field>
            <Field
              label="Model"
              hint={`${chosen ? `${chosen.note}. ` : ''}${
                chosen?.tier === 'paid'
                  ? 'Marked paid: it needs a key from a project with billing turned on.'
                  : 'Has a free tier. Your exact limits are shown in AI Studio.'
              }`}
            >
              <Select value={model} onChange={(e) => setModel(e.target.value)}>
                {models.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.label} ({m.tier === 'free' ? 'free tier' : 'paid'})
                  </option>
                ))}
              </Select>
            </Field>
            {saved?.gemini_key_source === 'settings' && (
              <Button type="button" variant="danger" onClick={removeKey} className="border border-red-200">
                Remove saved key
              </Button>
            )}
          </Card>
        )}

        {provider === 'ollama' && (
          <p className="text-sm text-slate-500">
            Using <code className="rounded bg-slate-100 px-1">{saved?.ollama_model}</code> through Ollama. Make sure Ollama is running.
          </p>
        )}

        {error && <p role="alert" className="rounded-md bg-red-50 p-3 text-sm text-red-700">{error}</p>}
        {notice && <p role="status" className="rounded-md bg-emerald-50 p-3 text-sm text-emerald-800">{notice}</p>}

        <div className="flex flex-wrap gap-2">
          <Button type="submit" disabled={busy || !dirty || needsKey}>
            {busy ? 'Working…' : 'Save'}
          </Button>
          <Button type="button" variant="secondary" onClick={runTest} disabled={busy || dirty}
            title={dirty ? 'Save your changes first' : undefined}>
            Test connection
          </Button>
        </div>
        {needsKey && <p className="text-xs text-slate-500">Paste a key to use Gemini.</p>}
      </form>
      </section>

 {test && (
        <p role="status" className={cn('rounded-md p-3 text-sm', test.ok ? 'bg-emerald-50 text-emerald-800' : 'bg-red-50 text-red-700')}>
          {test.ok ? `✓ ${test.provider} / ${test.model}, ${test.seconds}s. ${test.message}` : `✗ ${test.message}`}
        </p>
      )}

      {data && (
        <Card className="space-y-3">
          <h2 className="text-base font-semibold">Your data</h2>
          <p className="text-sm text-slate-600">
            Stored only on this computer: {data.sessions} interview{data.sessions === 1 ? '' : 's'}, {data.documents} document{data.documents === 1 ? '' : 's'},{' '}
            {data.answers} answer{data.answers === 1 ? '' : 's'}, {data.reports} report{data.reports === 1 ? '' : 's'} ({(data.upload_bytes / 1024).toFixed(0)} KB of uploads).
            You can delete one interview from the home page, or everything here. Your settings and API key are kept.
          </p>
          {dataNotice && (
            <p role="status" className="rounded-md bg-emerald-50 p-3 text-sm text-emerald-800">
              {dataNotice}
            </p>
          )}
          <Field label="Type DELETE ALL to enable the button">
            <Input value={confirmText} onChange={(e) => setConfirmText(e.target.value)} autoComplete="off" />
          </Field>
          <Button type="button" variant="danger" disabled={confirmText !== 'DELETE ALL' || data.sessions === 0} onClick={wipe} className="border border-red-200 disabled:border-slate-200 disabled:text-slate-400">
            Delete all my data
          </Button>
        </Card>
      )}
    </div>
  )
}
