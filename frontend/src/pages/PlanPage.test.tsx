import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { PlanPage } from './PlanPage'

const plan = {
  session_id: 's1', followup_budget: 3,
  topics: [
    { index: 0, category: 'intro', topic: 'Introduction and motivation', difficulty: 'easy' },
    { index: 1, category: 'gap', topic: 'Docker', difficulty: 'medium' },
    { index: 2, category: 'closing', topic: "Candidate's questions", difficulty: 'easy' },
  ],
}
const session = (focus: string[] | null) => ({ id: 's1', title: 'T', target_role: 'Dev', interview_type: 'mixed', difficulty: 'medium', question_count: 8, status: 'planned', created_at: '2026-10-20T10:00:00Z', overall_score: null, focus_topics: focus })

function setup(focus: string[] | null, planBody: unknown = plan, planStatus = 200) {
  vi.stubGlobal('fetch', vi.fn(async (url: string) => {
    const path = String(url).replace(/^\/api/, '')
    if (path === '/sessions/s1/plan') return new Response(JSON.stringify(planStatus === 200 ? planBody : { detail: 'No plan yet' }), { status: planStatus })
    if (path === '/sessions/s1') return new Response(JSON.stringify(session(focus)))
    return new Response('{}', { status: 404 })
  }))
  render(
    <MemoryRouter initialEntries={['/sessions/s1/plan']}>
      <Routes>
        <Route path="sessions/:sessionId/plan" element={<PlanPage />} />
        <Route path="sessions/:sessionId/interview" element={<p>INTERVIEW PAGE</p>} />
        <Route path="sessions/:sessionId/analysis" element={<p>ANALYSIS PAGE</p>} />
      </Routes>
    </MemoryRouter>,
  )
}
afterEach(() => vi.unstubAllGlobals())

describe('Plan page', () => {
  it('lists the topics in order and never shows any question text', async () => {
    setup(null)
    expect(await screen.findByText('Docker')).toBeInTheDocument()
    expect(screen.getByText('Gap area')).toBeInTheDocument()
    expect(screen.getAllByRole('listitem').length).toBeGreaterThanOrEqual(3)
    expect(screen.queryByText(/Practising your weak spots/)).not.toBeInTheDocument()
  })

  it('says which weak spots a "practise my weak spots" interview focuses on', async () => {
    setup(['Docker', 'SQL'])
    expect(await screen.findByText(/Practising your weak spots/)).toBeInTheDocument()
    expect(screen.getByText(/These topics come first: Docker, SQL/)).toBeInTheDocument()
  })

  it('shows a short "before you start" checklist, including a nudge about voice mode', async () => {
    setup(null)
    const tips = await screen.findByRole('region', { name: 'Before you start' })
    expect(tips).toHaveTextContent('Point first')
    expect(tips).toHaveTextContent('One to two minutes')
    expect(tips).toHaveTextContent('voice mode')
  })

  it('starts the interview', async () => {
    setup(null)
    await userEvent.click(await screen.findByRole('button', { name: 'Start interview' }))
    expect(await screen.findByText('INTERVIEW PAGE')).toBeInTheDocument()
  })

  it('points to the analysis when there is no plan yet', async () => {
    setup(null, null, 404)
    expect(await screen.findByText('There is no interview plan yet.')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Go to the analysis' })).toHaveAttribute('href', '/sessions/s1/analysis')
  })
})
