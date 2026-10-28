import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { vi } from 'vitest'
import { Upload } from './Upload'

const session = {
  id: 's1', title: 'Practice', target_role: 'Python Dev', interview_type: 'mixed',
  difficulty: 'medium', question_count: 10, status: 'created', created_at: '2026-01-01T00:00:00Z',
}
const doc = (over: object) => ({
  id: 'd1', session_id: 's1', kind: 'resume', filename: 'cv.pdf', status: 'ready',
  error: null, created_at: '2026-01-01T00:00:00Z', ...over,
})

function mockFetch(docs: object[]) {
  const fn = vi.fn(async (url: string, init?: RequestInit) => {
    const ok = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status })
    if (url.endsWith('/sessions/s1')) return ok(session)
    if (url.endsWith('/sessions/s1/documents') && init?.method === 'POST') return ok(doc({ status: 'uploaded' }), 202)
    if (url.endsWith('/sessions/s1/documents')) return ok(docs)
    if (url.includes('/documents/d1')) return ok({ ...doc({}), raw_text: 'Hello text', sections_json: [{ name: 'skills', text: 'x' }] })
    return ok({}, 404)
  })
  vi.stubGlobal('fetch', fn)
  return fn
}

const renderPage = () =>
  render(
    <MemoryRouter initialEntries={['/sessions/s1/upload']}>
      <Routes>
        <Route path="sessions/:sessionId/upload" element={<Upload />} />
      </Routes>
    </MemoryRouter>,
  )

afterEach(() => vi.unstubAllGlobals())

describe('Upload page', () => {
  it('shows session info and per-document status', async () => {
    mockFetch([doc({}), doc({ id: 'd2', kind: 'jd', filename: 'jd.txt', status: 'failed', error: 'No extractable text found' })])
    renderPage()
    expect(await screen.findByText('Practice')).toBeInTheDocument()
    expect(await screen.findByText('cv.pdf')).toBeInTheDocument()
    expect(screen.getByText('Ready')).toBeInTheDocument()
    expect(screen.getByText('Failed')).toBeInTheDocument()
    expect(screen.getByText('No extractable text found')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Analyse documents' })).toBeDisabled()
  })

  it('shows extracted text when a ready document is expanded', async () => {
    mockFetch([doc({})])
    renderPage()
    await userEvent.click(await screen.findByRole('button', { name: 'Text' }))
    expect(await screen.findByText('Hello text')).toBeInTheDocument()
    expect(screen.getByText('skills')).toBeInTheDocument()
  })

  it('rejects an unsupported file client-side without calling the API', async () => {
    const fetchFn = mockFetch([])
    renderPage()
    await screen.findByText('Practice')
    const input = screen.getByLabelText('Resume file') as HTMLInputElement
    await userEvent.upload(input, new File(['x'], 'cv.exe'), { applyAccept: false })
    expect(await screen.findByRole('alert')).toHaveTextContent('only .pdf, .docx, .txt')
    expect(fetchFn.mock.calls.some(([, init]) => (init as RequestInit | undefined)?.method === 'POST')).toBe(false)
  })

  it('uploads a valid file as the right kind', async () => {
    const fetchFn = mockFetch([])
    renderPage()
    await screen.findByText('Practice')
    await userEvent.upload(screen.getByLabelText('Resume file'), new File(['hello resume'], 'cv.txt'))
    await waitFor(() => {
      const post = fetchFn.mock.calls.find(([, init]) => (init as RequestInit | undefined)?.method === 'POST')
      expect(post).toBeTruthy()
      expect((post![1]!.body as FormData).get('kind')).toBe('resume')
    })
  })

  it('accepts a reused resume and enables analysis when the job description is ready', async () => {
    let documents = [doc({ id: 'jd1', kind: 'jd', filename: 'job.txt' })]
    const reused = doc({ id: 'resume2', kind: 'resume', filename: 'previous.pdf' })
    vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
      const ok = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status })
      if (url.endsWith('/reuse-options')) return ok([{ id: 'old-resume', filename: 'previous.pdf', session_title: 'Earlier attempt', kind: 'resume' }])
      if (url.endsWith('/documents/reuse') && init?.method === 'POST') {
        documents = [...documents, reused]
        return ok(reused, 201)
      }
      if (url.endsWith('/sessions/s1/documents')) return ok(documents)
      if (url.endsWith('/sessions/s1')) return ok(session)
      return ok({}, 404)
    }))
    renderPage()
    await userEvent.selectOptions(await screen.findByLabelText('Previous document'), 'old-resume')
    await userEvent.click(screen.getByRole('button', { name: 'Use selected document' }))
    await waitFor(() => expect(screen.getByRole('button', { name: 'Analyse documents' })).toBeEnabled())
    expect(screen.getByText('previous.pdf')).toBeInTheDocument()
  })

  it('shows an error page for an unknown session', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ detail: 'Session not found' }), { status: 404 })))
    renderPage()
    expect(await screen.findByRole('alert')).toHaveTextContent('Session not found')
  })
})
