import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { vi } from 'vitest'
import type { Analysis as AnalysisData } from '../lib/api'
import { Analysis } from './Analysis'

const ready: AnalysisData = {
  session_id: 's1', status: 'ready', error: null, model: 'mistral:7b', user_edited: false, warnings: [],
  updated_at: '2026-01-01T00:00:00Z',
  profile: {
    name: 'Asha Verma', total_experience_years: 5, current_role: 'Engineer',
    skills: [{ name: 'Python', level: 'advanced', evidence: 'x' }, { name: 'Docker', level: 'unknown', evidence: '' }],
    employers: [], projects: [{ title: 'Interview Bot', tech_stack: ['Python'], claimed_outcome: '' }], education: [], certifications: [],
  },
  requirements: {
    role_title: 'Python Dev', seniority: 'senior', must_have_skills: ['Python', 'Go'], nice_to_have_skills: [],
    responsibilities: [], domain: '', soft_skills: [],
  },
  gap: {
    matched_skills: ['Python'], gaps: ['Go'], nice_to_have_matched: [], nice_to_have_missing: [],
    claims_to_probe: [{ text: 'Docker', reason: 'No evidence' }], strengths: ['Python'], match_percent: 50,
  },
}

function stub(responses: Array<[number, unknown]>) {
  const queue = [...responses]
  const fn = vi.fn(async (_url: string, _init?: RequestInit) => {
    const [status, body] = queue.length > 1 ? queue.shift()! : queue[0]
    return new Response(JSON.stringify(body), { status })
  })
  vi.stubGlobal('fetch', fn)
  return fn
}

const renderPage = () =>
  render(
    <MemoryRouter initialEntries={['/sessions/s1/analysis']}>
      <Routes>
        <Route path="sessions/:sessionId/analysis" element={<Analysis />} />
      </Routes>
    </MemoryRouter>,
  )

afterEach(() => vi.unstubAllGlobals())

describe('Analysis page', () => {
  it('offers to start when no analysis exists', async () => {
    stub([[404, { detail: 'No analysis yet' }]])
    renderPage()
    expect(await screen.findByText('No analysis yet.')).toBeInTheDocument()
  })

  it('shows progress while running', async () => {
    stub([[200, { ...ready, status: 'running', profile: null, requirements: null, gap: null }]])
    renderPage()
    expect(await screen.findByRole('status')).toHaveTextContent('Analysing your documents')
  })

  it('shows the error and a retry button when failed', async () => {
    stub([[200, { ...ready, status: 'failed', error: 'Cannot reach Ollama', profile: null, requirements: null, gap: null }]])
    renderPage()
    expect(await screen.findByRole('alert')).toHaveTextContent('Cannot reach Ollama')
    expect(screen.getByRole('button', { name: 'Try again' })).toBeInTheDocument()
  })

  it('renders the match summary and gaps', async () => {
    stub([[200, ready]])
    renderPage()
    expect(await screen.findByText('50% of must-haves matched')).toBeInTheDocument()
    expect(screen.getAllByText('Go').length).toBeGreaterThan(0)
    expect(screen.getByText(/No evidence/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Save changes' })).toBeDisabled()
  })

  it('saves an edited skill list via PATCH and shows the refreshed gap', async () => {
    const updated = { ...ready, user_edited: true, gap: { ...ready.gap!, matched_skills: ['Python', 'Go'], gaps: [], match_percent: 100 } }
    const fetchFn = stub([[200, ready], [200, updated]])
    renderPage()
    await userEvent.click(await screen.findByRole('button', { name: 'Remove Docker' }))
    const save = screen.getByRole('button', { name: 'Save changes' })
    expect(save).toBeEnabled()
    await userEvent.click(save)

    await waitFor(() => expect(screen.getByText('100% of must-haves matched')).toBeInTheDocument())
    const patch = fetchFn.mock.calls.find(([, init]) => init?.method === 'PATCH')!
    const sent = JSON.parse(patch[1]!.body as string)
    expect(sent.profile.skills.map((s: { name: string }) => s.name)).toEqual(['Python'])
    expect(sent.requirements.must_have_skills).toEqual(['Python', 'Go'])
  })

  it('adds a skill with Enter', async () => {
    stub([[200, ready]])
    renderPage()
    await userEvent.type(await screen.findByLabelText('Add to Skills'), 'Redis{Enter}')
    expect(screen.getByText('Redis')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Save changes' })).toBeEnabled()
  })
})
