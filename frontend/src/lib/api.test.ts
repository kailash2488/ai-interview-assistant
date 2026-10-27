import { vi } from 'vitest'
import { api, ApiError, AUTH_EXPIRED } from './api'

function respond(status: number, body: unknown = {}) {
  const fn = vi.fn(async () => new Response(JSON.stringify(body), { status }))
  vi.stubGlobal('fetch', fn)
  return fn
}
afterEach(() => vi.unstubAllGlobals())

describe('api client and sessions', () => {
  it('sends the session cookie with every request', async () => {
    const fn = respond(200, [])
    await api.listSessions()
    expect((fn.mock.calls[0] as unknown as [string, RequestInit])[1].credentials).toBe('include')
  })

  it('announces an ended session on 401 from a normal call', async () => {
    respond(401, { detail: 'Please sign in' })
    const seen = vi.fn()
    window.addEventListener(AUTH_EXPIRED, seen)
    await expect(api.listSessions()).rejects.toBeInstanceOf(ApiError)
    expect(seen).toHaveBeenCalledTimes(1)
    window.removeEventListener(AUTH_EXPIRED, seen)
  })

  it('does not treat a wrong password or the startup check as an ended session', async () => {
    const seen = vi.fn()
    window.addEventListener(AUTH_EXPIRED, seen)
    respond(401, { detail: 'Wrong email or password' })
    await expect(api.login({ email: 'a@b.co', password: 'x' })).rejects.toThrow('Wrong email or password')
    respond(401, { detail: 'Please sign in' })
    expect(await api.me()).toBeNull()
    expect(seen).not.toHaveBeenCalled()
    window.removeEventListener(AUTH_EXPIRED, seen)
  })

  it('surfaces other errors from me()', async () => {
    respond(500, { detail: 'boom' })
    await expect(api.me()).rejects.toThrow('boom')
  })
})
