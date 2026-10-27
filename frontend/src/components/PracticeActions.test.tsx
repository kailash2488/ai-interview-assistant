import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { PracticeActions } from './PracticeActions'

function setup(weak: string[]) {
  render(
    <MemoryRouter initialEntries={['/start']}>
      <Routes>
        <Route path="/start" element={<PracticeActions sessionId="s1" weak={weak} />} />
        <Route path="/sessions/:id/plan" element={<p>PLAN PAGE</p>} />
      </Routes>
    </MemoryRouter>,
  )
}
afterEach(() => vi.unstubAllGlobals())

describe('PracticeActions', () => {
  it('starts a copy with the chosen focus, builds its plan, then opens it', async () => {
    const calls: Array<[string, string | undefined, unknown]> = []
    vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
      calls.push([String(url), init?.method, init?.body ? JSON.parse(String(init.body)) : undefined])
      return new Response(JSON.stringify({ id: 'new1' }), { status: 201 })
    }))
    setup(['Docker', 'SQL'])
    expect(screen.getByText(/Weak spots to focus on: Docker, SQL/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /Practise my weak spots/ }))
    expect(await screen.findByText('PLAN PAGE')).toBeInTheDocument()
    expect(calls[0]).toEqual(['/api/sessions/s1/retry', 'POST', { focus: 'weak', topics: ['Docker', 'SQL'] }]) // the topics shown are the ones used
    expect(calls[1][0]).toBe('/api/sessions/new1/plan')
  })

  it('can repeat the same interview', async () => {
    const fetchFn = vi.fn(async () => new Response(JSON.stringify({ id: 'n2' }), { status: 201 }))
    vi.stubGlobal('fetch', fetchFn)
    setup([])
    await userEvent.click(screen.getByRole('button', { name: /Try the same interview again/ }))
    await screen.findByText('PLAN PAGE')
    expect(JSON.parse(String((fetchFn.mock.calls[0] as unknown as [string, RequestInit])[1].body))).toEqual({ focus: 'same' })
  })

  it('disables the weak-spot button when nothing scored below 60', () => {
    setup([])
    expect(screen.getByRole('button', { name: /Practise my weak spots/ })).toBeDisabled()
  })

  it('shows why it failed and lets the user try again', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ detail: 'Analyse the documents of this interview first' }), { status: 409 })))
    setup(['Docker'])
    await userEvent.click(screen.getByRole('button', { name: /Practise my weak spots/ }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Analyse the documents')
    await waitFor(() => expect(screen.getByRole('button', { name: /Practise my weak spots/ })).toBeEnabled())
  })
})
