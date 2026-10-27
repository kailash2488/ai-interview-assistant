import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { AuthContext } from '../lib/auth'
import type { Dashboard, Session } from '../lib/api'
import { Home } from './Home'

const USER = { id: 'u1', email: 'ada@example.com', name: 'Ada Lovelace', created_at: '2026-01-01T00:00:00Z' }
const session = (over: Partial<Session> = {}): Session => ({ id: 's1', title: 'Backend practice', target_role: 'Python Dev', interview_type: 'mixed', difficulty: 'medium', question_count: 8, status: 'reported', created_at: '2026-10-20T10:00:00Z', overall_score: 72, focus_topics: null, ...over })

const empty: Dashboard = {
  stats: { interviews: 0, finished: 0, reports: 0, avg_score: null, best_score: null, latest_score: null, change: null, streak_days: 0, practice_days_30: 0, answers: 0 },
  trend: [], weakest: [], strongest: [], dimensions: [], recent: [],
  next_action: { kind: 'new', title: null, label: 'Start a new interview', description: 'Upload a resume and a job description.', session_id: null, href: '/new' },
  badges: [{ id: 'first', label: 'First interview', description: 'Finish your first mock interview', earned: false }],
}
const full: Dashboard = {
  stats: { interviews: 2, finished: 2, reports: 2, avg_score: 66, best_score: 72, latest_score: 72, change: 12, streak_days: 3, practice_days_30: 5, answers: 17 },
  trend: [
    { session_id: 's0', title: 'First', target_role: 'Dev', date: '2026-10-18T10:00:00Z', score: 60 },
    { session_id: 's1', title: 'Backend practice', target_role: 'Dev', date: '2026-10-20T10:00:00Z', score: 72 },
  ],
  weakest: [{ name: 'Docker', score: 30, attempts: 2 }, { name: 'SQL', score: 55, attempts: 1 }, { name: 'Python', score: 80, attempts: 2 }],
  strongest: [{ name: 'Python', score: 80, attempts: 2 }],
  dimensions: [{ key: 'depth', label: 'Depth', score: 55, change: 10 }, { key: 'evidence', label: 'Evidence', score: 40, change: -5 }],
  recent: [],
  next_action: { kind: 'continue', title: 'Backend practice', label: 'Continue your interview', description: 'You are partway through it.', session_id: 's1', href: '/sessions/s1/interview' },
  badges: [{ id: 'first', label: 'First interview', description: 'Finish your first mock interview', earned: true }],
}

function mock(dashboard: Dashboard, sessions: Session[], failDashboard = false) {
  const calls: Array<[string, string]> = []
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
    const path = String(url).replace(/^\/api/, '')
    calls.push([init?.method ?? 'GET', path])
    if (path === '/dashboard') return failDashboard ? new Response(JSON.stringify({ detail: 'boom' }), { status: 500 }) : new Response(JSON.stringify(dashboard))
    if (path === '/sessions' && !init?.method) return new Response(JSON.stringify(sessions))
    if (init?.method === 'DELETE') return new Response(null, { status: 204 })
    return new Response('{}', { status: 404 })
  }))
  return calls
}

function renderHome() {
  const value = { user: USER, loading: false, signup: vi.fn(), login: vi.fn(), logout: vi.fn(), forget: vi.fn() }
  return render(<MemoryRouter><AuthContext.Provider value={value}><Home /></AuthContext.Provider></MemoryRouter>)
}
afterEach(() => vi.unstubAllGlobals())

describe('Home dashboard', () => {
  it('greets the user and never looks empty for a brand-new account', async () => {
    mock(empty, [])
    renderHome()
    expect(await screen.findByRole('heading', { name: 'Hi Ada, ready to practise?' })).toBeInTheDocument()
    expect(await screen.findByRole('region', { name: 'Suggested next step' })).toHaveTextContent('Start a new interview')
    expect(screen.getByRole('heading', { name: 'How it works' })).toBeInTheDocument() // onboarding instead of empty charts
    expect(screen.getByRole('complementary', { name: 'Interview tip' })).toBeInTheDocument()
    expect(screen.getByText('No interviews yet. Your first one will appear here.')).toBeInTheDocument()
    expect(screen.getAllByText('—').length).toBeGreaterThan(0) // numbers that do not exist yet read as a dash, not a fake zero
  })

  it('shows the numbers, trend, topics to work on and milestones once there are reports', async () => {
    mock(full, [session(), session({ id: 's0', title: 'First', overall_score: 60 })])
    renderHome()
    const numbers = await screen.findByRole('region', { name: 'Your numbers' })
    expect(within(numbers).getByText('▲ +12')).toBeInTheDocument()
    expect(within(numbers).getByText('3 days')).toBeInTheDocument()
    expect(within(numbers).getByText('17')).toBeInTheDocument()
    expect(screen.getByRole('img', { name: /Score over time: 2 interviews, latest 72/ })).toBeInTheDocument()
    expect(screen.getByRole('list', { name: 'Topics to work on' })).toHaveTextContent('Docker')
    expect(screen.getByText(/Strongest:/)).toHaveTextContent('Python (80)')
    expect(screen.getByRole('list', { name: 'How you answer (latest report)' })).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'How it works' })).not.toBeInTheDocument()
    expect(screen.getByText('1 of 1')).toBeInTheDocument()
  })

  it('offers to practise the weak spots (below 60) from the latest report', async () => {
    mock(full, [session()])
    renderHome()
    expect(await screen.findByText(/Weak spots to focus on: Docker, SQL\./)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Practise my weak spots/ })).toBeEnabled()
  })

  it('lists every interview with its stage, score and focus, linking to the right next page', async () => {
    mock(empty, [
      session({ id: 'a', title: 'Reported one', status: 'reported', overall_score: 85, focus_topics: ['Docker'] }),
      session({ id: 'b', title: 'In the middle', status: 'in_progress', overall_score: null }),
      session({ id: 'c', title: 'Needs upload', status: 'created', overall_score: null }),
    ])
    renderHome()
    expect(await screen.findByRole('link', { name: /Reported one/ })).toHaveAttribute('href', '/sessions/a/report')
    expect(screen.getByRole('link', { name: /In the middle/ })).toHaveAttribute('href', '/sessions/b/interview')
    expect(screen.getByRole('link', { name: /Needs upload/ })).toHaveAttribute('href', '/sessions/c/upload')
    expect(screen.getByText('Score 85')).toBeInTheDocument()
    expect(screen.getByText('In progress')).toBeInTheDocument()
    expect(screen.getByText('Draft')).toBeInTheDocument()
    expect(screen.getByText('Focus: Docker')).toBeInTheDocument()
  })

  it('deletes an interview only after confirmation and refreshes', async () => {
    const calls = mock(empty, [session({ id: 'z', title: 'Delete me' })])
    const confirm = vi.spyOn(window, 'confirm').mockReturnValueOnce(false).mockReturnValueOnce(true)
    renderHome()
    const button = await screen.findByRole('button', { name: 'Delete Delete me' })
    await userEvent.click(button)
    expect(calls.some(([m]) => m === 'DELETE')).toBe(false)
    await userEvent.click(button)
    await vi.waitFor(() => expect(calls.some(([m, p]) => m === 'DELETE' && p === '/sessions/z')).toBe(true))
    expect(confirm).toHaveBeenCalledTimes(2)
  })

  it('shows a clear error when the dashboard cannot be loaded', async () => {
    mock(empty, [], true)
    renderHome()
    expect(await screen.findByRole('alert')).toHaveTextContent('boom')
  })
})
