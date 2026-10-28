import { Laptop, Moon, Sun } from 'lucide-react'
import { useEffect, useState } from 'react'
import { applyTheme, saveTheme, storedTheme, type ThemePreference } from '../lib/theme'

const OPTIONS: Array<{ value: ThemePreference; label: string; icon: typeof Sun }> = [
  { value: 'light', label: 'Light', icon: Sun },
  { value: 'dark', label: 'Dark', icon: Moon },
  { value: 'system', label: 'System', icon: Laptop },
]

export function ThemeToggle({ compact = false }: { compact?: boolean }) {
  const [theme, setTheme] = useState<ThemePreference>(storedTheme)

  useEffect(() => {
    applyTheme(theme)
    const media = window.matchMedia?.('(prefers-color-scheme: dark)')
    if (!media) return
    const sync = () => theme === 'system' && applyTheme('system')
    media.addEventListener('change', sync)
    return () => media.removeEventListener('change', sync)
  }, [theme])

  if (compact) {
    const current = OPTIONS.find((option) => option.value === theme)!
    const Icon = current.icon
    return <button type="button" aria-label={`Theme: ${current.label}. Change theme`} title={`Theme: ${current.label}`} onClick={() => {
      const next = OPTIONS[(OPTIONS.findIndex((option) => option.value === theme) + 1) % OPTIONS.length].value
      saveTheme(next); setTheme(next)
    }} className="inline-flex size-9 items-center justify-center rounded-full text-slate-600 transition-colors hover:bg-slate-100 hover:text-slate-900"><Icon className="size-4.5" /></button>
  }

  return <div className="inline-flex rounded-xl border border-slate-200 bg-slate-50 p-1" aria-label="Colour theme">
    {OPTIONS.map(({ value, label, icon: Icon }) => <button key={value} type="button" aria-pressed={theme === value} onClick={() => { saveTheme(value); setTheme(value) }} className={`inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-medium transition-colors ${theme === value ? 'bg-white text-brand-700 shadow-sm' : 'text-slate-500 hover:text-slate-800'}`}><Icon className="size-3.5" />{label}</button>)}
  </div>
}
