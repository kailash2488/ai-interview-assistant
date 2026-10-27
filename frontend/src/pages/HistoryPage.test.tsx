import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { vi } from 'vitest'
import type { Comparison, HistoryItem } from '../lib/api'
import { HistoryPage } from './HistoryPage'

const item = (id: string, title: string, score: number): HistoryItem => ({
  session_id: id, title, target_role: 'Python Dev', created_at: '2026-01-01T10:00:00Z', overall_score: score, verdict: 'Good', evaluated: 8,
})
const attempt = (id: string, title: string, score: number) => ({ session_id: id, title, target_role: 'Python Dev', created_at: '2026-01-01T10:00:00Z', overall_score: score, verdict: 'Good', avg_words: 60 })
const comparison: Comparison = {
  a: attempt('a', 'First try', 50), b: attempt('b', 'Second try', 72), overall_delta: 22, same_role: true,
  dimensions: [{ name: 'Depth', a: 40, b: 70, delta: 30 }, { name: 'Evidence', a: 60, b: 55, delta: -5 }],
  areas: [{ name: 'Python', a: 60, b: 80, delta: 20 }, { name: 'Docker', a: null, b: 50, delta: null }],
}

function stub(routes: Record<string, [number, unknown]>) {
  const fn = vi.fn(async (url: string) => {
    const key = Object.keys(routes).find((k) => String(url).includes(k))
    const [status, body] = key ? routes[key] : [404, { detail: 'x' }]
    return new Response(JSON.stringify(body), { status })
  })
  vi.stubGlobal('fetch', fn)
  return fn
}
const renderAt = (path = '/history') =>
  render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="history" element={<HistoryPage />} />
      </Routes>
    </MemoryRouter>,
  )
afterEach(() => vi.unstubAllGlobals())

describe('History page', () => {
  it('shows an empty state without finished reports', async () => {
    stub({ '/history': [200, []] })
    renderAt()
    expect(await screen.findByText('No finished reports yet.')).toBeInTheDocument()
  })

  it('charts the attempts and asks for a second one before comparing', async () => {
    stub({ '/history': [200, [item('a', 'First try', 50)]] })
    renderAt()
    expect(await screen.findByRole('list', { name: 'Overall score by attempt' })).toBeInTheDocument()
    expect(screen.getByText('Finish and score a second interview to compare.')).toBeInTheDocument()
  })

  it('compares two attempts and shows signed changes, not colour alone', async () => {
    stub({ '/history/compare': [200, comparison], '/history': [200, [item('a', 'First try', 50), item('b', 'Second try', 72)]] })
    renderAt('/history?a=a&b=b')
    expect(await screen.findByText('50 → 72')).toBeInTheDocument()
    expect(screen.getAllByText('▲ +22').length).toBe(1)
    const dims = within(screen.getByRole('heading', { name: 'By rubric dimension' }).closest('div')!)
    expect(dims.getByText('▲ +30')).toBeInTheDocument()
    expect(dims.getByText('▼ -5')).toBeInTheDocument()
    expect(screen.getByText('n/a')).toBeInTheDocument() // Docker only in the later attempt
  })

  it('picking two attempts triggers the comparison', async () => {
    const fetchFn = stub({ '/history/compare': [200, comparison], '/history': [200, [item('a', 'First try', 50), item('b', 'Second try', 72)]] })
    renderAt()
    await userEvent.selectOptions(await screen.findByLabelText('Earlier attempt'), 'a')
    await userEvent.selectOptions(screen.getByLabelText('Later attempt'), 'b')
    expect(await screen.findByText('50 → 72')).toBeInTheDocument()
    expect(fetchFn.mock.calls.some(([u]) => String(u).includes('/history/compare?a=a&b=b'))).toBe(true)
  })

  it('warns when the roles differ and shows server errors', async () => {
    stub({ '/history/compare': [200, { ...comparison, same_role: false }], '/history': [200, [item('a', 'x', 1), item('b', 'y', 2)]] })
    renderAt('/history?a=a&b=b')
    expect(await screen.findByText(/different roles/)).toBeInTheDocument()
    vi.unstubAllGlobals()
    stub({ '/history/compare': [409, { detail: '"y" has no finished report yet' }], '/history': [200, [item('a', 'x', 1), item('b', 'y', 2)]] })
    renderAt('/history?a=a&b=b')
    await waitFor(() => expect(screen.getAllByRole('alert').some((n) => n.textContent?.includes('no finished report'))).toBe(true))
  })
})
