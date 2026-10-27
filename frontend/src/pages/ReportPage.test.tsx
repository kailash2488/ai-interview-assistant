import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { vi } from 'vitest'
import type { Report } from '../lib/api'
import { ReportPage } from './ReportPage'

const dim = (score: number, quote = '') => ({ score, quote, verified: !!quote })
const ready: Report = {
  session_id: 's1', status: 'ready', error: null, model: 'gemini-3.5-flash-lite', warnings: [], progress_done: 2, progress_total: 2,
  overall_score: 72, updated_at: '2026-01-01T00:00:00Z',
  report: {
    overall_score: 72, verdict: 'Good - close to ready', verdict_basis: 'Based on 2 evaluated answers.', target_role: 'Python Dev',
    summary: 'Solid production experience.', dimension_scores: { technical_accuracy: 80, depth: 55, relevance: 90, structure_clarity: 70, evidence: 60 },
    areas: [
      { name: 'Docker', category: 'gap', score_percent: 30, answers: 1 },
      { name: 'Python', category: 'core', score_percent: 85, answers: 2 },
    ],
    strengths: [{ title: 'Python depth', detail: 'You explained trade-offs.' }],
    improvements: [{ title: 'Docker basics', detail: 'Review images and layers.' }],
    questions: [{
      order_no: 2, topic: 'Python', category: 'core', is_follow_up: false, question: 'How do you use asyncio?', answer: 'I use it for IO-bound work.',
      answer_summary: 'Uses asyncio for IO.', score_percent: 85,
      dimensions: { technical_accuracy: dim(4, 'IO-bound work'), depth: dim(3), relevance: dim(5, 'I use it'), structure_clarity: dim(4), evidence: dim(2) },
      missing_points: ['thread pool for blocking calls'], feedback: 'Good start, mention blocking calls.', sample_answer: 'I use asyncio for IO-bound services.',
      notes: ['depth: capped at 2 because the answer was very short'],
    }],
    communication: { answers: 2, avg_words: 55, shortest_words: 40, longest_words: 70, one_line_answers: 0, rambling_answers: 0, filler_words: {}, vague_phrases: {}, avg_seconds: 45, observations: ['Your answer length was in a good range.'] },
    improvement_plan: [{ timeframe: 'Week 1', focus: 'Docker', actions: ['Build an image', 'Read the layers guide'] }],
    coverage: { planned_topics: 6, questions_asked: 6, evaluated: 2, unanswered: 1 },
  },
}

function stub(handler: (url: string, init?: RequestInit) => [number, unknown]) {
  const fn = vi.fn(async (url: string, init?: RequestInit) => {
    const [status, body] = handler(url, init)
    return new Response(JSON.stringify(body), { status })
  })
  vi.stubGlobal('fetch', fn)
  return fn
}
const renderPage = () =>
  render(
    <MemoryRouter initialEntries={['/sessions/s1/report']}>
      <Routes>
        <Route path="sessions/:sessionId/report" element={<ReportPage />} />
      </Routes>
    </MemoryRouter>,
  )
afterEach(() => vi.unstubAllGlobals())

describe('Report page', () => {
  it('does not generate anything until the user clicks the button', async () => {
    const fetchFn = stub((_u, init) => (init?.method === 'POST' ? [202, { ...ready, status: 'running', report: null }] : [404, { detail: 'No report yet' }]))
    renderPage()
    const button = await screen.findByRole('button', { name: 'Generate feedback report' })
    expect(fetchFn.mock.calls.some(([, i]) => i?.method === 'POST')).toBe(false)
    await userEvent.click(button)
    expect(await screen.findByRole('status')).toHaveTextContent('Evaluating your answers')
    expect(fetchFn.mock.calls.filter(([, i]) => i?.method === 'POST')).toHaveLength(1)
  })

  it('shows progress while running', async () => {
    stub(() => [200, { ...ready, status: 'running', report: null, progress_done: 3, progress_total: 8 }])
    renderPage()
    expect(await screen.findByRole('status')).toHaveTextContent('3 of 8 answers evaluated')
    expect(screen.getByLabelText('Evaluation progress')).toHaveAttribute('value', '3')
  })

  it('shows the failure and a retry button', async () => {
    stub(() => [200, { ...ready, status: 'failed', error: 'Cannot reach Ollama', report: null }])
    renderPage()
    expect(await screen.findByRole('alert')).toHaveTextContent('Cannot reach Ollama')
    expect(screen.getByRole('button', { name: 'Try again' })).toBeInTheDocument()
  })

  it('shows a reason when generating is refused', async () => {
    stub((_u, init) => (init?.method === 'POST' ? [409, { detail: 'Finish the interview before generating a report' }] : [404, { detail: 'none' }]))
    renderPage()
    await userEvent.click(await screen.findByRole('button', { name: 'Generate feedback report' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Finish the interview')
  })

  it('renders the finished report', async () => {
    stub(() => [200, ready])
    renderPage()
    expect(await screen.findByLabelText('Overall score 72 out of 100')).toBeInTheDocument()
    expect(screen.getByText('Good - close to ready')).toBeInTheDocument()
    expect(screen.getByText(/2 of 6 planned topics were scored; 1 question was left unanswered/)).toBeInTheDocument()
    expect(screen.getByText('Python depth')).toBeInTheDocument()
    expect(screen.getByText('Docker basics')).toBeInTheDocument()
    expect(screen.getByText('Week 1: Docker')).toBeInTheDocument()
    // topics are sorted best first
    const items = within(screen.getByRole('list', { name: 'Score by topic' })).getAllByRole('listitem')
    expect(items[0]).toHaveTextContent('Python')
    expect(items[1]).toHaveTextContent('Docker')
  })

  it('expands a question to show feedback, evidence quotes, guard notes and the sample answer', async () => {
    stub(() => [200, ready])
    renderPage()
    await userEvent.click(await screen.findByRole('button', { name: /2\. Python/ }))
    expect(screen.getByText('Good start, mention blocking calls.')).toBeInTheDocument()
    expect(screen.getByText('“IO-bound work”')).toBeInTheDocument()
    expect(screen.getByText('thread pool for blocking calls')).toBeInTheDocument()
    expect(screen.getByText(/capped at 2 because the answer was very short/)).toBeInTheDocument()
    expect(screen.getByText('I use asyncio for IO-bound services.')).toBeInTheDocument()
    expect(screen.getAllByText('No supporting quote').length).toBe(3)
  })

  it('asks before replacing the report, then regenerates', async () => {
    const confirm = vi.spyOn(window, 'confirm').mockReturnValueOnce(false).mockReturnValueOnce(true)
    const fetchFn = stub((_u, init) => (init?.method === 'POST' ? [202, { ...ready, status: 'running', report: null }] : [200, ready]))
    renderPage()
    const regen = await screen.findByRole('button', { name: 'Regenerate' })
    await userEvent.click(regen)
    expect(fetchFn.mock.calls.some(([, i]) => i?.method === 'POST')).toBe(false)
    await userEvent.click(regen)
    await waitFor(() => expect(fetchFn.mock.calls.some(([, i]) => i?.method === 'POST')).toBe(true))
    expect(confirm).toHaveBeenCalledTimes(2)
  })

  it('shows warnings when the written summary was built from scores', async () => {
    stub(() => [200, { ...ready, warnings: ['The written summary could not be generated.'] }])
    renderPage()
    expect(await screen.findByText('The written summary could not be generated.')).toBeInTheDocument()
  })
})
