import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { vi } from 'vitest'
import { StrictMode } from 'react'
import { MCQPage } from './MCQPage'

const question = { question_id: 'q1', order_no: 1, topic: 'Python', text: 'Which statement is correct?', options: ['Correct choice', 'Wrong B', 'Wrong C', 'Wrong D'], selected_index: null, correct: null, correct_index: null, explanation: null }

afterEach(() => vi.unstubAllGlobals())

it('runs an MCQ and reveals the explanation only after completion', async () => {
  const fetch = vi.fn(async (url: string, init?: RequestInit) => {
    if (url.endsWith('/mcq') && !init?.method) return new Response(JSON.stringify({ session_id: 's1', status: 'planned', total: 1, answered: 0, score: null, current: null, results: [] }))
    if (url.endsWith('/start')) return new Response(JSON.stringify({ session_id: 's1', status: 'in_progress', total: 1, answered: 0, score: null, current: question, results: [] }), { status: 201 })
    return new Response(JSON.stringify({ session_id: 's1', status: 'completed', total: 1, answered: 1, score: 100, current: null, results: [{ ...question, selected_index: 0, correct: true, correct_index: 0, explanation: 'It directly satisfies the requirement.' }] }))
  })
  vi.stubGlobal('fetch', fetch)
  render(<StrictMode><MemoryRouter initialEntries={['/sessions/s1/mcq']}><Routes><Route path="/sessions/:sessionId/mcq" element={<MCQPage />} /></Routes></MemoryRouter></StrictMode>)
  expect(await screen.findByText('Which statement is correct?')).toBeInTheDocument()
  expect(screen.queryByText(/directly satisfies/)).not.toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: /Correct choice/ }))
  await userEvent.click(screen.getByRole('button', { name: 'Lock answer & continue' }))
  expect(await screen.findByText('100%')).toBeInTheDocument()
  expect(screen.getByText(/directly satisfies/)).toBeInTheDocument()
  const answerRequest = fetch.mock.calls.find(([url]) => String(url).endsWith('/answer'))
  expect(JSON.parse(String(answerRequest?.[1]?.body))).toEqual({ question_id: 'q1', selected_index: 0 })
  expect(fetch.mock.calls.filter(([url]) => String(url).endsWith('/start'))).toHaveLength(1)
})
