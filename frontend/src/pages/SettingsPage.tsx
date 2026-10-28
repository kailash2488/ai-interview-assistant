import { useEffect, useState, type FormEvent } from 'react'
import { Bot, BrainCircuit, Check, ChevronRight, Cloud, ExternalLink, HardDrive, KeyRound, LockKeyhole, ServerCog, ShieldCheck, Sparkles, Trash2, Zap } from 'lucide-react'
import { AccountCard } from '../components/AccountCard'
import { Button } from '../components/ui/button'
import { Card } from '../components/ui/card'
import { Field, Input, Select } from '../components/ui/field'
import { api, type DataSummary, type LLMSettings, type LLMTestResult, type Provider } from '../lib/api'
import { useOptionalAuth } from '../lib/auth'
import { cn } from '../lib/utils'

const PROVIDERS: Array<{ id: Provider; name: string; short: string; icon: typeof Bot; badge: string; accent: string }> = [
  { id: 'ollama', name: 'Local model (Ollama)', short: 'Private models on your computer', icon: HardDrive, badge: 'Local & free', accent: 'from-emerald-500 to-teal-600' },
  { id: 'gemini', name: 'Google Gemini', short: 'Fast with a generous free tier', icon: Sparkles, badge: 'Popular', accent: 'from-blue-500 to-indigo-600' },
  { id: 'openai', name: 'OpenAI', short: 'GPT models for reliable interviews', icon: Bot, badge: 'Cloud', accent: 'from-slate-700 to-slate-950' },
  { id: 'anthropic', name: 'Anthropic', short: 'Claude models with strong reasoning', icon: BrainCircuit, badge: 'Cloud', accent: 'from-orange-500 to-amber-600' },
  { id: 'azure', name: 'Azure OpenAI', short: 'Your enterprise Azure deployment', icon: Cloud, badge: 'Enterprise', accent: 'from-cyan-500 to-blue-700' },
]
const META: Record<Exclude<Provider, 'ollama'>, { keyLabel: string; link: string; linkText: string; privacy: string }> = {
  gemini: { keyLabel: 'Gemini API key', link: 'https://aistudio.google.com/apikey', linkText: 'Google AI Studio', privacy: 'Documents are sent to Google.' },
  openai: { keyLabel: 'OpenAI API key', link: 'https://platform.openai.com/api-keys', linkText: 'OpenAI API keys', privacy: 'Documents are sent to OpenAI.' },
  anthropic: { keyLabel: 'Anthropic API key', link: 'https://console.anthropic.com/settings/keys', linkText: 'Anthropic Console', privacy: 'Documents are sent to Anthropic.' },
  azure: { keyLabel: 'Azure API key', link: 'https://portal.azure.com', linkText: 'Azure Portal', privacy: 'Documents are sent to your Azure OpenAI resource.' },
}

export function SettingsPage() {
  const auth = useOptionalAuth()
  const [saved, setSaved] = useState<LLMSettings | null>(null)
  const [provider, setProvider] = useState<Provider>('ollama')
  const [geminiModel, setGeminiModel] = useState('gemini-3.5-flash-lite')
  const [model, setModel] = useState('')
  const [key, setKey] = useState('')
  const [endpoint, setEndpoint] = useState('')
  const [apiVersion, setApiVersion] = useState('2024-10-21')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [test, setTest] = useState<LLMTestResult | null>(null)
  const [data, setData] = useState<DataSummary | null>(null)
  const [confirmText, setConfirmText] = useState('')
  const [dataNotice, setDataNotice] = useState<string | null>(null)

  const modelFor = (s: LLMSettings, p: Provider) => p === 'openai' ? s.openai_model : p === 'anthropic' ? s.anthropic_model : p === 'azure' ? s.azure_model : ''
  function adopt(s: LLMSettings) {
    const selected = s.provider === 'ollama' && !s.ollama_enabled ? 'gemini' : s.provider
    if (!s.ollama_enabled) {
      const ollamaIndex = PROVIDERS.findIndex((item) => item.id === 'ollama')
      if (ollamaIndex >= 0) PROVIDERS.splice(ollamaIndex, 1)
    }
    setSaved(s); setProvider(selected); setGeminiModel(s.gemini_model); setModel(modelFor(s, selected))
    setEndpoint(s.azure_endpoint); setApiVersion(s.azure_api_version); setKey('')
  }
  useEffect(() => {
    api.getLLMSettings().then(adopt).catch((e) => setError(e instanceof Error ? e.message : 'Failed to load settings'))
    api.getDataSummary().then(setData).catch(() => undefined)
  }, [])
  function choose(p: Provider) { setProvider(p); setModel(saved ? modelFor(saved, p) : ''); setKey(''); setTest(null); setNotice(null) }

  async function save(e: FormEvent) {
    e.preventDefault(); setBusy(true); setError(null); setNotice(null); setTest(null)
    try {
      const body = { provider, gemini_model: geminiModel,
        ...(key.trim() ? provider === 'gemini' ? { gemini_api_key: key.trim() } : { api_key: key.trim() } : {}),
        ...(provider !== 'ollama' && provider !== 'gemini' ? { model: model.trim() } : {}),
        ...(provider === 'azure' ? { azure_endpoint: endpoint.trim(), azure_api_version: apiVersion.trim() } : {}) }
      adopt(await api.saveLLMSettings(body)); setNotice('Saved. New AI tasks will use this provider.')
    } catch (err) { setError(err instanceof Error ? err.message : 'Could not save settings') } finally { setBusy(false) }
  }
  async function runTest() {
    setBusy(true); setTest(null); setError(null)
    try { setTest(await api.testLLM()) } catch (err) { setError(err instanceof Error ? err.message : 'Connection test failed') } finally { setBusy(false) }
  }
  async function removeKey() {
    const fallback = saved?.ollama_enabled ? 'Ollama' : 'Gemini configuration'
    if (provider === 'ollama' || !window.confirm(`Remove the saved ${PROVIDERS.find((p) => p.id === provider)?.name} key and switch to ${fallback}?`)) return
    try { adopt(await (provider === 'gemini' ? api.removeGeminiKey() : api.removeProviderKey(provider))); setNotice('Credential removed securely.') } catch (err) { setError(err instanceof Error ? err.message : 'Could not remove the key') }
  }
  async function wipe() {
    try { setData(await api.deleteAllData()); setConfirmText(''); setDataNotice('All interviews, documents, answers and reports were deleted.') }
    catch (err) { setError(err instanceof Error ? err.message : 'Could not delete your data') }
  }

  if (!saved && !error) return <div className="flex min-h-64 items-center justify-center text-slate-500">Loading your workspace…</div>
  const cloud = provider !== 'ollama'
  const meta = cloud ? META[provider] : null
  const keySet = cloud && (!!saved?.key_set?.[provider] || (provider === 'gemini' && !!saved?.gemini_key_set))
  const keyHint = cloud ? saved?.key_hint?.[provider] ?? (provider === 'gemini' ? saved?.gemini_key_hint : null) : null
  const dirty = !!saved && (provider !== saved.provider || geminiModel !== saved.gemini_model || (cloud && provider !== 'gemini' && model !== modelFor(saved, provider)) || key.trim() !== '' || (provider === 'azure' && (endpoint !== saved.azure_endpoint || apiVersion !== saved.azure_api_version)))
  const needs = cloud && ((!keySet && !key.trim()) || (provider !== 'gemini' && !model.trim()) || (provider === 'azure' && !endpoint.trim()))

  return <div className="space-y-8">
    <section className="relative overflow-hidden rounded-[2rem] bg-gradient-to-br from-slate-950 via-indigo-950 to-brand-800 p-7 text-white shadow-lift sm:p-10">
      <div aria-hidden className="absolute -right-20 -top-24 size-80 rounded-full bg-fuchsia-500/20 blur-3xl" />
      <div className="relative max-w-3xl"><p className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-[.18em] text-indigo-200"><ServerCog className="size-4" /> AI workspace</p><h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">Settings that put you in control</h1><p className="mt-3 text-sm leading-6 text-indigo-100 sm:text-base">Choose where interviews run, manage credentials safely, and understand exactly where your data goes.</p></div>
    </section>
    <div className="grid gap-8 xl:grid-cols-[minmax(0,1fr)_360px]">
      <div className="space-y-8">
        <section aria-labelledby="provider-title" className="space-y-5"><div><p className="text-xs font-semibold uppercase tracking-[.16em] text-brand-600">Step 1</p><h2 id="provider-title" className="mt-1 text-2xl font-semibold">Choose your AI provider</h2><p className="mt-1 text-sm text-slate-500">Switch at any time. Existing reports do not change.</p></div>
          <div className="grid gap-4 sm:grid-cols-2 2xl:grid-cols-3">{PROVIDERS.map((p) => { const Icon = p.icon; const active = provider === p.id; return <label key={p.id} className={cn('group relative cursor-pointer overflow-hidden rounded-2xl border bg-white p-5 shadow-card transition-all hover:-translate-y-1 hover:shadow-lift', active ? 'border-brand-400 ring-4 ring-brand-500/10' : 'border-slate-200')}><input className="sr-only" type="radio" name="provider" checked={active} onChange={() => choose(p.id)} aria-label={p.name} /><div className="flex items-start justify-between"><span className={cn('flex size-11 items-center justify-center rounded-xl bg-gradient-to-br text-white shadow-sm', p.accent)}><Icon className="size-5" /></span>{active ? <span className="flex size-6 items-center justify-center rounded-full bg-brand-600 text-white"><Check className="size-4" /></span> : <ChevronRight className="size-5 text-slate-300 group-hover:text-brand-500" />}</div><div className="mt-4 flex items-center gap-2"><h3 className="font-semibold">{p.name}</h3><span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-slate-500">{p.badge}</span></div><p className="mt-1 text-sm text-slate-500">{p.short}</p></label>})}</div>
        </section>
        <form onSubmit={save} className="space-y-5"><Card className="space-y-5 border-slate-200/70 p-6 sm:p-8"><div className="flex items-start gap-4"><span className="flex size-11 items-center justify-center rounded-xl bg-brand-50 text-brand-600"><KeyRound className="size-5" /></span><div><p className="text-xs font-semibold uppercase tracking-[.16em] text-brand-600">Step 2</p><h2 className="text-xl font-semibold">Configure {PROVIDERS.find((p) => p.id === provider)?.name}</h2></div></div>
          {provider === 'ollama' ? <div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-5"><div className="flex gap-3"><ShieldCheck className="size-6 shrink-0 text-emerald-600" /><div><p className="font-semibold text-emerald-950">Private by default</p><p className="mt-1 text-sm text-emerald-800">Using <code className="rounded bg-white/70 px-1.5 py-0.5">{saved?.ollama_model}</code>. No API key required; documents stay on this computer.</p></div></div></div> : <>
            <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl bg-slate-50 p-4 text-sm"><span className="flex items-center gap-2 text-slate-600"><LockKeyhole className="size-4 text-emerald-600" /> Keys are encrypted and never shown again.</span><a href={meta!.link} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 font-medium text-brand-600 hover:underline">Get a key at {meta!.linkText}<ExternalLink className="size-3.5" /></a></div>
            <Field label={meta!.keyLabel} hint={keySet ? `A key ending ${keyHint ?? ''} is saved. Leave blank to keep it.` : 'Paste your provider key. It is encrypted before storage.'}><Input type="password" autoComplete="off" spellCheck={false} value={key} onChange={(e) => setKey(e.target.value)} placeholder={keySet ? '••••••••••••' : 'Paste API key'} /></Field>
            {provider === 'gemini' ? <Field label="Model" hint={(saved?.gemini_models.find((m) => m.id === geminiModel)?.tier === 'paid') ? 'Marked paid: it needs a key from a project with billing turned on.' : 'Has a free tier. Your exact limits are shown in AI Studio.'}><Select value={geminiModel} onChange={(e) => setGeminiModel(e.target.value)}>{saved?.gemini_models.map((m) => <option key={m.id} value={m.id}>{m.label} ({m.tier === 'free' ? 'free tier' : 'paid'})</option>)}</Select></Field> : <Field label={provider === 'azure' ? 'Deployment name' : 'Model ID'} hint={provider === 'openai' ? 'Example: gpt-4o-mini' : provider === 'anthropic' ? 'Example: claude-3-5-haiku-latest' : 'The deployment name from Azure AI Foundry.'}><Input value={model} onChange={(e) => setModel(e.target.value)} placeholder={provider === 'openai' ? 'gpt-4o-mini' : provider === 'anthropic' ? 'claude-3-5-haiku-latest' : 'my-gpt-deployment'} /></Field>}
            {provider === 'azure' && <div className="grid gap-4 sm:grid-cols-2"><Field label="Azure endpoint"><Input type="url" value={endpoint} onChange={(e) => setEndpoint(e.target.value)} placeholder="https://resource.openai.azure.com" /></Field><Field label="API version"><Input value={apiVersion} onChange={(e) => setApiVersion(e.target.value)} /></Field></div>}
            <p className="flex items-start gap-2 rounded-xl border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900"><Cloud className="mt-0.5 size-4 shrink-0" />{meta!.privacy} Review the provider's retention policy before using sensitive information.</p></>}
          {error && <p role="alert" className="rounded-xl bg-red-50 p-3 text-sm text-red-700">{error}</p>}{notice && <p role="status" className="rounded-xl bg-emerald-50 p-3 text-sm text-emerald-800">{notice}</p>}
          <div className="flex flex-wrap gap-3 border-t border-slate-100 pt-5"><Button type="submit" disabled={busy || !dirty || needs}>{busy ? 'Working…' : 'Save'}</Button><Button type="button" variant="secondary" onClick={runTest} disabled={busy || dirty}><Zap className="size-4" /> Test connection</Button>{cloud && keySet && <Button type="button" variant="ghost" onClick={removeKey} className="ml-auto text-red-600 hover:bg-red-50"><Trash2 className="size-4" /> Remove saved key</Button>}</div>{needs && <p className="text-xs text-slate-500">{provider === 'gemini' ? 'Paste a key to use Gemini.' : 'Complete the required credentials and model fields to save.'}</p>}</Card>
          {test && <p role="status" className={cn('rounded-xl border p-4 text-sm', test.ok ? 'border-emerald-200 bg-emerald-50 text-emerald-800' : 'border-red-200 bg-red-50 text-red-700')}>{test.ok ? `✓ Connected to ${test.provider} / ${test.model} in ${test.seconds}s. ${test.message}` : `✗ ${test.message}`}</p>}
        </form>
      </div>
      <aside className="space-y-6">{auth?.user && <AccountCard />}<Card className="space-y-4"><div className="flex items-center gap-3"><ServerCog className="size-5 text-brand-600" /><h2 className="font-semibold">Current setup</h2></div><div className="rounded-xl bg-slate-50 p-4"><p className="text-xs uppercase tracking-wide text-slate-500">Active provider</p><p className="mt-1 font-semibold">{PROVIDERS.find((p) => p.id === saved?.provider)?.name}</p></div><ul className="space-y-2 text-sm text-slate-600"><li className="flex gap-2"><Check className="mt-0.5 size-4 text-emerald-600" /> Per-account configuration</li><li className="flex gap-2"><Check className="mt-0.5 size-4 text-emerald-600" /> Encrypted credentials</li><li className="flex gap-2"><Check className="mt-0.5 size-4 text-emerald-600" /> Connection verification</li></ul></Card>
        {data && <Card className="space-y-4"><h2 className="font-semibold">Your data</h2><p className="text-sm leading-6 text-slate-600">{data.sessions} interview{data.sessions === 1 ? '' : 's'}, {data.documents} document{data.documents === 1 ? '' : 's'}, {data.answers} answer{data.answers === 1 ? '' : 's'}, {data.reports} report{data.reports === 1 ? '' : 's'} stored locally.</p>{dataNotice && <p role="status" className="rounded-lg bg-emerald-50 p-3 text-xs text-emerald-800">{dataNotice}</p>}<Field label="Type DELETE ALL to erase interview data"><Input value={confirmText} onChange={(e) => setConfirmText(e.target.value)} autoComplete="off" /></Field><Button type="button" variant="danger" disabled={confirmText !== 'DELETE ALL' || data.sessions === 0} onClick={wipe} className="w-full"><Trash2 className="size-4" /> Delete all my data</Button></Card>}
      </aside>
    </div>
  </div>
}
