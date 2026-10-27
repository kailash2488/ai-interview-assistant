import { Link } from 'react-router-dom'

export function LogoMark({ className = 'size-8' }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" className={className} aria-hidden>
      <defs>
        <linearGradient id="lg" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#6366f1" />
          <stop offset="1" stopColor="#a855f7" />
        </linearGradient>
      </defs>
      <rect width="32" height="32" rx="9" fill="url(#lg)" />
      <path d="M9 11.5A2.5 2.5 0 0 1 11.5 9h9a2.5 2.5 0 0 1 2.5 2.5v6a2.5 2.5 0 0 1-2.5 2.5H15l-3.6 3v-3h0A2.5 2.5 0 0 1 9 17.5z" fill="#fff" />
      <path d="M13 13.5h6M13 16.5h3.5" stroke="#6366f1" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  )
}

export function Logo({ to = '/', light = false }: { to?: string; light?: boolean }) {
  return (
    <Link to={to} className="flex items-center gap-2.5 whitespace-nowrap text-[15px] font-semibold tracking-tight sm:text-base">
      <LogoMark />
      <span className={light ? 'text-white' : 'text-slate-900'}>
        AI Interview <span className={light ? 'text-brand-300' : 'text-brand-600'}>Assistant</span>
      </span>
    </Link>
  )
}
