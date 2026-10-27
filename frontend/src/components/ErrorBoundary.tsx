import { Component, type ErrorInfo, type ReactNode } from 'react'

interface State {
  failed: boolean
}

/** Last line of defence: a rendering bug shows a message with a way out instead of a blank page. */
export class ErrorBoundary extends Component<{ children: ReactNode }, State> {
  state: State = { failed: false }

  static getDerivedStateFromError(): State {
    return { failed: true }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('Unhandled UI error', error, info.componentStack)
  }

  render() {
    if (!this.state.failed) return this.props.children
    return (
      <div role="alert" className="mx-auto max-w-xl space-y-3 rounded-xl border border-red-200 bg-white p-6">
        <h1 className="text-lg font-semibold text-red-700">Something went wrong</h1>
        <p className="text-sm text-slate-600">Your interviews and answers are saved. Reload the page to continue.</p>
        <button
          type="button"
          className="rounded-md bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700"
          onClick={() => window.location.assign('/')}
        >
          Back to home
        </button>
      </div>
    )
  }
}
