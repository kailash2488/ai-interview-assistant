import type { ReactNode } from 'react'
import { BrowserRouter, Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { ErrorBoundary } from './components/ErrorBoundary'
import { AppShell } from './components/Layout'
import { AuthProvider, useAuth } from './lib/auth'
import { Analysis } from './pages/Analysis'
import { AuthPage } from './pages/AuthPage'
import { HistoryPage } from './pages/HistoryPage'
import { Home } from './pages/Home'
import { Interview } from './pages/Interview'
import { Landing } from './pages/Landing'
import { MCQPage } from './pages/MCQPage'
import { PlanPage } from './pages/PlanPage'
import { ReportPage } from './pages/ReportPage'
import { SettingsPage } from './pages/SettingsPage'
import { Setup } from './pages/Setup'
import { Upload } from './pages/Upload'

function Splash() {
  return (
    <div className="flex min-h-screen items-center justify-center text-sm text-slate-400" role="status">
      Loading…
    </div>
  )
}

/** Signed-out visitors are sent to the login page and brought back afterwards. */
function RequireAuth({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth()
  const location = useLocation()
  if (loading) return <Splash />
  if (!user) return <Navigate to={`/login?next=${encodeURIComponent(location.pathname + location.search)}`} replace />
  return <>{children}</>
}

/** "/" is the marketing page for visitors and the interview list for signed-in users. */
function Root() {
  const { user, loading } = useAuth()
  if (loading) return <Splash />
  return user ? (
    <AppShell>
      <Home />
    </AppShell>
  ) : (
    <Landing />
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <ErrorBoundary>
        <AuthProvider>
          <Routes>
            <Route index element={<Root />} />
            <Route path="login" element={<AuthPage mode="login" />} />
            <Route path="signup" element={<AuthPage mode="signup" />} />
            <Route
              element={
                <RequireAuth>
                  <AppShell />
                </RequireAuth>
              }
            >
              <Route path="new" element={<Setup />} />
              <Route path="sessions/:sessionId/upload" element={<Upload />} />
              <Route path="sessions/:sessionId/analysis" element={<Analysis />} />
              <Route path="sessions/:sessionId/plan" element={<PlanPage />} />
              <Route path="sessions/:sessionId/interview" element={<Interview />} />
              <Route path="sessions/:sessionId/mcq" element={<MCQPage />} />
              <Route path="sessions/:sessionId/report" element={<ReportPage />} />
              <Route path="history" element={<HistoryPage />} />
              <Route path="settings" element={<SettingsPage />} />
              <Route path="*" element={<p className="text-slate-500">Page not found.</p>} />
            </Route>
          </Routes>
        </AuthProvider>
      </ErrorBoundary>
    </BrowserRouter>
  )
}
