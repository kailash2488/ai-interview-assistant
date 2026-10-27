import type { ReactNode } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import { cn } from '../lib/utils'
import { Logo } from './Logo'
import { UserMenu } from './UserMenu'

const NAV = [
  { to: '/', label: 'Interviews', end: true },
  { to: '/history', label: 'Progress', end: false },
  { to: '/settings', label: 'Settings', end: false },
]

/** The signed-in app frame. Pages render in the <Outlet/> (or as children for the home route). */
export function AppShell({ children }: { children?: ReactNode }) {
  return (
    <div className="bg-glow min-h-screen">
      <header className="sticky top-0 z-20 border-b border-slate-200/70 bg-white/80 backdrop-blur-md">
        <div className="mx-auto flex h-16 w-full max-w-[1600px] items-center justify-between gap-6 px-4 sm:px-6 lg:px-8">
          <div className="flex items-center gap-8">
            <Logo />
            <nav aria-label="Main" className="hidden items-center gap-1 sm:flex">
              {NAV.map((n) => (
                <NavLink
                  key={n.to}
                  to={n.to}
                  end={n.end}
                  className={({ isActive }) =>
                    cn('rounded-lg px-3 py-1.5 text-sm font-medium transition-colors', isActive ? 'bg-brand-50 text-brand-700' : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900')
                  }
                >
                  {n.label}
                </NavLink>
              ))}
            </nav>
          </div>
          <UserMenu />
        </div>
        <nav aria-label="Main (mobile)" className="flex gap-1 border-t border-slate-100 px-3 py-1.5 sm:hidden">
          {NAV.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              end={n.end}
              className={({ isActive }) => cn('flex-1 rounded-lg px-3 py-1.5 text-center text-sm font-medium', isActive ? 'bg-brand-50 text-brand-700' : 'text-slate-600')}
            >
              {n.label}
            </NavLink>
          ))}
        </nav>
      </header>
      <main className="mx-auto w-full max-w-[1600px] px-4 py-8 sm:px-6 sm:py-10 lg:px-8 xl:px-10">{children ?? <Outlet />}</main>
    </div>
  )
}
