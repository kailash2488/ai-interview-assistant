import { LogOut, Settings as SettingsIcon } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../lib/auth'

export function Avatar({ name, className = 'size-9 text-sm' }: { name: string; className?: string }) {
  const initial = (name.trim()[0] ?? '?').toUpperCase()
  return (
    <span aria-hidden className={`inline-flex items-center justify-center rounded-full bg-gradient-to-br from-brand-500 to-fuchsia-500 font-semibold text-white ${className}`}>
      {initial}
    </span>
  )
}

export function UserMenu() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const close = (e: MouseEvent) => !ref.current?.contains(e.target as Node) && setOpen(false)
    const esc = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false)
    document.addEventListener('mousedown', close)
    document.addEventListener('keydown', esc)
    return () => {
      document.removeEventListener('mousedown', close)
      document.removeEventListener('keydown', esc)
    }
  }, [open])

  if (!user) return null
  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label="Account menu"
        className="flex items-center gap-2 rounded-full p-0.5 pr-2 transition-colors hover:bg-slate-100 focus-visible:outline-2 focus-visible:outline-brand-500"
      >
        <Avatar name={user.name} />
        <span className="hidden max-w-32 truncate text-sm font-medium text-slate-700 sm:block">{user.name}</span>
      </button>
      {open && (
        <div role="menu" className="absolute right-0 z-30 mt-2 w-64 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-lift">
          <div className="border-b border-slate-100 px-4 py-3">
            <p className="truncate text-sm font-semibold text-slate-900">{user.name}</p>
            <p className="truncate text-xs text-slate-500">{user.email}</p>
          </div>
          <div className="p-1.5">
            <Link role="menuitem" to="/settings" onClick={() => setOpen(false)} className="flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm text-slate-700 hover:bg-slate-50">
              <SettingsIcon className="size-4 text-slate-400" /> Settings
            </Link>
            <button
              role="menuitem"
              type="button"
              onClick={async () => {
                setOpen(false)
                await logout()
                navigate('/')
              }}
              className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-left text-sm text-slate-700 hover:bg-slate-50"
            >
              <LogOut className="size-4 text-slate-400" /> Log out
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
