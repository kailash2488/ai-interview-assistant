import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { vi } from 'vitest'
import { AuthContext } from '../lib/auth'
import { AccountCard } from './AccountCard'

const USER = { id: 'u1', email: 'ada@example.com', name: 'Ada Lovelace', created_at: '2026-01-01T00:00:00Z' }

function setup(forget = vi.fn()) {
  const value = { user: USER, loading: false, signup: vi.fn(), login: vi.fn(), logout: vi.fn(), forget }
  render(
    <MemoryRouter>
      <AuthContext.Provider value={value}>
        <AccountCard />
      </AuthContext.Provider>
    </MemoryRouter>,
  )
  return forget
}

function stub(status: number, body: unknown = {}) {
  const fn = vi.fn(async () => new Response(status === 204 ? null : JSON.stringify(body), { status }))
  vi.stubGlobal('fetch', fn)
  return fn
}
afterEach(() => vi.unstubAllGlobals())

describe('AccountCard', () => {
  it('shows who is signed in', () => {
    setup()
    expect(screen.getByRole('heading', { name: 'Ada Lovelace' })).toBeInTheDocument()
    expect(screen.getByText('ada@example.com')).toBeInTheDocument()
  })

  it('changes the password and tells the user other devices were signed out', async () => {
    const fetchFn = stub(204)
    setup()
    await userEvent.type(screen.getByLabelText('Current password'), 'old password')
    await userEvent.type(screen.getByLabelText('New password'), 'a brand new password')
    await userEvent.click(screen.getByRole('button', { name: 'Change password' }))
    expect(await screen.findByRole('status')).toHaveTextContent('other devices were signed out')
    const call = fetchFn.mock.calls[0] as unknown as [string, RequestInit]
    expect(call[0]).toMatch(/\/auth\/change-password$/)
    expect(JSON.parse(call[1].body as string)).toEqual({ current_password: 'old password', new_password: 'a brand new password' })
    expect(screen.getByLabelText('Current password')).toHaveValue('')
  })

  it('rejects a short new password without calling the server', async () => {
    const fetchFn = stub(204)
    setup()
    await userEvent.type(screen.getByLabelText('Current password'), 'old password')
    await userEvent.type(screen.getByLabelText('New password'), 'short')
    await userEvent.click(screen.getByRole('button', { name: 'Change password' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('at least 8 characters')
    expect(fetchFn).not.toHaveBeenCalled()
  })

  it('shows the server error for a wrong current password', async () => {
    stub(403, { detail: 'Your current password is wrong' })
    setup()
    await userEvent.type(screen.getByLabelText('Current password'), 'nope nope')
    await userEvent.type(screen.getByLabelText('New password'), 'a brand new password')
    await userEvent.click(screen.getByRole('button', { name: 'Change password' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Your current password is wrong')
  })

  it('deletes the account only after a password and a confirmation', async () => {
    const confirm = vi.spyOn(window, 'confirm').mockReturnValueOnce(false).mockReturnValueOnce(true)
    const fetchFn = stub(204)
    const forget = setup()
    const button = screen.getByRole('button', { name: 'Delete my account' })
    expect(button).toBeDisabled()
    await userEvent.type(screen.getByLabelText('Your password'), 'correct password')
    await userEvent.click(button)
    expect(fetchFn).not.toHaveBeenCalled() // the user said no
    await userEvent.click(button)
    await waitFor(() => expect(forget).toHaveBeenCalled())
    const call = fetchFn.mock.calls[0] as unknown as [string, RequestInit]
    expect(call[1].method).toBe('DELETE')
    expect(JSON.parse(call[1].body as string)).toEqual({ password: 'correct password' })
    expect(confirm).toHaveBeenCalledTimes(2)
  })

  it('keeps the account and shows the reason when the password is wrong', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    stub(403, { detail: 'Your password is wrong' })
    const forget = setup()
    await userEvent.type(screen.getByLabelText('Your password'), 'wrong')
    await userEvent.click(screen.getByRole('button', { name: 'Delete my account' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Your password is wrong')
    expect(forget).not.toHaveBeenCalled()
  })
})
