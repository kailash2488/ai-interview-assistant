import { act, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi } from 'vitest'
import App from './App'
import { AUTH_EXPIRED } from './lib/api'

const USER = { id: 'u1', email: 'ada@example.com', name: 'Ada Lovelace', created_at: '2026-01-01T00:00:00Z' }

interface World {
  user: typeof USER | null
  allowSignup: boolean
  loginStatus: number
  signupStatus: number
  calls: Array<{ method: string; path: string; body: unknown }>
}

function installWorld(partial: Partial<World> = {}): World {
  const world: World = { user: null, allowSignup: true, loginStatus: 200, signupStatus: 201, calls: [], ...partial }
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string, init?: RequestInit) => {
      const path = String(url).replace(/^\/api/, '')
      const method = init?.method ?? 'GET'
      const body = typeof init?.body === 'string' ? JSON.parse(init.body) : undefined
      world.calls.push({ method, path, body })
      const json = (data: unknown, status = 200) => new Response(JSON.stringify(data), { status })
      if (path === '/auth/me') return world.user ? json(world.user) : json({ detail: 'Please sign in' }, 401)
      if (path === '/auth/config') return json({ allow_signup: world.allowSignup })
      if (path === '/auth/login') {
        if (world.loginStatus !== 200) return json({ detail: 'Wrong email or password' }, world.loginStatus)
        world.user = USER
        return json(USER)
      }
      if (path === '/auth/signup') {
        if (world.signupStatus !== 201) return json({ detail: 'An account with this email already exists. Log in instead.' }, world.signupStatus)
        world.user = { ...USER, name: body.name, email: body.email }
        return json(world.user, 201)
      }
      if (path === '/auth/logout') {
        world.user = null
        return new Response(null, { status: 204 })
      }
      if (path === '/sessions') return json([])
      if (path === '/history') return json([])
      return json({ detail: 'not mocked' }, 404)
    }),
  )
  return world
}

function visit(path: string) {
  window.history.pushState({}, '', path)
  return render(<App />)
}

afterEach(() => {
  vi.unstubAllGlobals()
  window.history.pushState({}, '', '/')
})

describe('landing page and routing', () => {
  it('shows the landing page to visitors who are not signed in', async () => {
    installWorld()
    visit('/')
    expect(await screen.findByRole('heading', { level: 1, name: /Practice the interview/ })).toBeInTheDocument()
    expect(screen.getAllByRole('link', { name: /Get started|Start practising free|Create your account/ }).length).toBeGreaterThan(0)
    expect(screen.getAllByRole('link', { name: 'Log in' }).length).toBeGreaterThan(0)
    expect(screen.getByRole('heading', { name: /Everything you need to prepare/ })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Good questions' })).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Your interviews' })).not.toBeInTheDocument()
  })

  it('does not overclaim: the privacy section tells the truth about Gemini', async () => {
    installWorld()
    visit('/')
    await screen.findByRole('heading', { level: 1 })
    expect(screen.getByText(/Your documents are sent to Google/)).toBeInTheDocument()
    expect(screen.getByText(/never leaves your computer/i)).toBeInTheDocument()
  })

  it('sends signed-out visitors from a protected page to login and remembers where they were going', async () => {
    installWorld()
    visit('/history')
    expect(await screen.findByRole('heading', { name: 'Welcome back' })).toBeInTheDocument()
    expect(window.location.pathname).toBe('/login')
    expect(window.location.search).toBe('?next=%2Fhistory')
  })

  it('shows the app to a signed-in user', async () => {
    installWorld({ user: USER })
    visit('/')
    expect(await screen.findByRole('heading', { name: 'Your interviews' })).toBeInTheDocument()
    expect(screen.getByText(/Welcome back, Ada/)).toBeInTheDocument()
    expect(screen.queryByRole('heading', { level: 1, name: /Practice the interview/ })).not.toBeInTheDocument()
  })

  it('keeps signed-in users away from the login page', async () => {
    installWorld({ user: USER })
    visit('/login')
    expect(await screen.findByRole('heading', { name: 'Your interviews' })).toBeInTheDocument()
    expect(window.location.pathname).toBe('/')
  })
})

describe('login', () => {
  it('logs in and returns to the page the user wanted', async () => {
    const world = installWorld()
    visit('/history')
    await userEvent.type(await screen.findByLabelText('Email'), 'ada@example.com')
    await userEvent.type(screen.getByLabelText('Password'), 'a long password')
    await userEvent.click(screen.getByRole('button', { name: 'Log in' }))
    expect(await screen.findByRole('heading', { name: 'Your progress' })).toBeInTheDocument()
    expect(window.location.pathname).toBe('/history')
    expect(world.calls.find((c) => c.path === '/auth/login')?.body).toEqual({ email: 'ada@example.com', password: 'a long password' })
  })

  it('shows the server error and stays on the page', async () => {
    installWorld({ loginStatus: 401 })
    visit('/login')
    await userEvent.type(await screen.findByLabelText('Email'), 'ada@example.com')
    await userEvent.type(screen.getByLabelText('Password'), 'wrong password')
    await userEvent.click(screen.getByRole('button', { name: 'Log in' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Wrong email or password')
    expect(window.location.pathname).toBe('/login')
  })

  it('validates before calling the server', async () => {
    const world = installWorld()
    visit('/login')
    await userEvent.type(await screen.findByLabelText('Email'), 'not-an-email')
    await userEvent.click(screen.getByRole('button', { name: 'Log in' }))
    expect(await screen.findByText('Enter a valid email address')).toBeInTheDocument()
    expect(screen.getByText('Enter your password')).toBeInTheDocument()
    expect(world.calls.some((c) => c.path === '/auth/login')).toBe(false)
  })

  it('ignores a next parameter that points off the site', async () => {
    installWorld()
    visit('/login?next=//evil.example/steal')
    await userEvent.type(await screen.findByLabelText('Email'), 'ada@example.com')
    await userEvent.type(screen.getByLabelText('Password'), 'a long password')
    await userEvent.click(screen.getByRole('button', { name: 'Log in' }))
    expect(await screen.findByRole('heading', { name: 'Your interviews' })).toBeInTheDocument()
    expect(window.location.pathname).toBe('/')
  })

  it('can show and hide the password', async () => {
    installWorld()
    visit('/login')
    const field = await screen.findByLabelText('Password')
    expect(field).toHaveAttribute('type', 'password')
    await userEvent.click(screen.getByRole('button', { name: 'Show password' }))
    expect(field).toHaveAttribute('type', 'text')
    await userEvent.click(screen.getByRole('button', { name: 'Hide password' }))
    expect(field).toHaveAttribute('type', 'password')
  })
})

describe('signup', () => {
  it('creates an account and lands in the app', async () => {
    const world = installWorld()
    visit('/signup')
    await userEvent.type(await screen.findByLabelText('Name'), 'Grace Hopper')
    await userEvent.type(screen.getByLabelText('Email'), 'grace@example.com')
    await userEvent.type(screen.getByLabelText('Password'), 'eight chars+')
    await userEvent.click(screen.getByRole('button', { name: 'Create account' }))
    expect(await screen.findByText(/Welcome back, Grace/)).toBeInTheDocument()
    expect(world.calls.find((c) => c.path === '/auth/signup')?.body).toEqual({ email: 'grace@example.com', name: 'Grace Hopper', password: 'eight chars+' })
  })

  it('checks name, email and password length in the browser', async () => {
    const world = installWorld()
    visit('/signup')
    await userEvent.type(await screen.findByLabelText('Email'), 'nope')
    await userEvent.type(screen.getByLabelText('Password'), 'short')
    await userEvent.click(screen.getByRole('button', { name: 'Create account' }))
    expect(await screen.findByText('Enter your name')).toBeInTheDocument()
    expect(screen.getByText('Enter a valid email address')).toBeInTheDocument()
    expect(screen.getByText('Use at least 8 characters')).toBeInTheDocument()
    expect(world.calls.some((c) => c.path === '/auth/signup')).toBe(false)
  })

  it('offers a login link when the email is already registered', async () => {
    installWorld({ signupStatus: 409 })
    visit('/signup')
    await userEvent.type(await screen.findByLabelText('Name'), 'Ada')
    await userEvent.type(screen.getByLabelText('Email'), 'ada@example.com')
    await userEvent.type(screen.getByLabelText('Password'), 'a long password')
    await userEvent.click(screen.getByRole('button', { name: 'Create account' }))
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('already exists')
    expect(alert.querySelector('a')).toHaveAttribute('href', '/login')
  })

  it('says so when sign-ups are closed and hides the form', async () => {
    installWorld({ allowSignup: false })
    visit('/signup')
    expect(await screen.findByText(/Sign-ups are closed on this server/)).toBeInTheDocument()
    expect(screen.queryByLabelText('Name')).not.toBeInTheDocument()
  })
})

describe('session handling', () => {
  it('logs out from the account menu and returns to the landing page', async () => {
    installWorld({ user: USER })
    visit('/')
    await userEvent.click(await screen.findByRole('button', { name: 'Account menu' }))
    expect(screen.getByText('ada@example.com')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('menuitem', { name: /Log out/ }))
    expect(await screen.findByRole('heading', { level: 1, name: /Practice the interview/ })).toBeInTheDocument()
  })

  it('sends the user to login when the session ends while using the app', async () => {
    installWorld({ user: USER })
    visit('/history')
    await screen.findByRole('heading', { name: 'Your progress' })
    act(() => {
      window.dispatchEvent(new Event(AUTH_EXPIRED))
    })
    await waitFor(() => expect(window.location.pathname).toBe('/login'))
    expect(await screen.findByRole('heading', { name: 'Welcome back' })).toBeInTheDocument()
  })

  it('closes the account menu with Escape', async () => {
    installWorld({ user: USER })
    visit('/')
    await userEvent.click(await screen.findByRole('button', { name: 'Account menu' }))
    expect(screen.getByRole('menu')).toBeInTheDocument()
    await userEvent.keyboard('{Escape}')
    expect(screen.queryByRole('menu')).not.toBeInTheDocument()
  })
})
