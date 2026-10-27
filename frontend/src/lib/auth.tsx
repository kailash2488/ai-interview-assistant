import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { api, AUTH_EXPIRED, type User } from './api'

interface AuthState {
  user: User | null
  loading: boolean
  signup: (body: { email: string; name: string; password: string }) => Promise<void>
  login: (body: { email: string; password: string }) => Promise<void>
  logout: () => Promise<void>
  /** The account was deleted: drop the signed-in user without calling the server again. */
  forget: () => void
}

export const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    api
      .me()
      .then((u) => !cancelled && setUser(u))
      .catch(() => !cancelled && setUser(null))
      .finally(() => !cancelled && setLoading(false))
    const expired = () => setUser(null)
    window.addEventListener(AUTH_EXPIRED, expired)
    return () => {
      cancelled = true
      window.removeEventListener(AUTH_EXPIRED, expired)
    }
  }, [])

  const signup = useCallback(async (body: { email: string; name: string; password: string }) => setUser(await api.signup(body)), [])
  const login = useCallback(async (body: { email: string; password: string }) => setUser(await api.login(body)), [])
  const logout = useCallback(async () => {
    try {
      await api.logout()
    } finally {
      setUser(null)
    }
  }, [])

  const forget = useCallback(() => setUser(null), [])
  const value = useMemo(() => ({ user, loading, signup, login, logout, forget }), [user, loading, signup, login, logout, forget])
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>')
  return ctx
}

/** For components that work with or without a signed-in context (for example in isolated tests). */
export function useOptionalAuth(): AuthState | null {
  return useContext(AuthContext)
}
