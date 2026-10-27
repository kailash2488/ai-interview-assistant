import { act, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { vi } from 'vitest'
import type { ServerMessage } from '../lib/api'
import { Interview } from './Interview'

class MockSocket {
  static instances: MockSocket[] = []
  sent: Array<{ type: string; text?: string }> = []
  onmessage: ((ev: { data: string }) => void) | null = null
  onclose: (() => void) | null = null
  url: string
  constructor(url: string) {
    this.url = url
    MockSocket.instances.push(this)
  }
  send(data: string) {
    this.sent.push(JSON.parse(data))
  }
  close() {}
  push(msg: ServerMessage | { type: string; [k: string]: unknown }) {
    act(() => this.onmessage?.({ data: JSON.stringify(msg) }))
  }
}

const question = (id: string, no: number, text: string, extra: object = {}) => ({
  type: 'question' as const, question_id: id, order_no: no, topic: 'T', text, ack: '', is_follow_up: false, replay: false,
  progress: { main_asked: no, main_total: 10 }, ...extra,
})

const emptyState = { type: 'state' as const, session_id: 's1', status: 'planned', main_total: 10, main_asked: 0, turns: [] }

function setup() {
  MockSocket.instances = []
  vi.stubGlobal('WebSocket', MockSocket)
  render(
    <MemoryRouter initialEntries={['/sessions/s1/interview']}>
      <Routes>
        <Route path="sessions/:sessionId/interview" element={<Interview />} />
      </Routes>
    </MemoryRouter>,
  )
  return MockSocket.instances[0]
}

afterEach(() => vi.unstubAllGlobals())

describe('Interview room', () => {
  it('connects to the interview socket and starts when nothing was asked yet', () => {
    const ws = setup()
    expect(ws.url).toMatch(/^ws:\/\/.*\/api\/sessions\/s1\/interview$/)
    ws.push(emptyState)
    expect(ws.sent).toEqual([{ type: 'start' }])
  })

  it('shows streamed tokens, then replaces them with the final question', async () => {
    const ws = setup()
    ws.push(emptyState)
    ws.push(question('q1', 1, 'Please introduce yourself.'))
    expect(screen.getByText('Please introduce yourself.')).toBeInTheDocument()
    expect(screen.getByLabelText('progress')).toHaveTextContent('Question 1 of 10')

    await userEvent.type(screen.getByLabelText('Your answer'), 'I am a backend engineer')
    await userEvent.click(screen.getByRole('button', { name: 'Send answer' }))
    expect(ws.sent.at(-1)).toEqual({ type: 'answer', text: 'I am a backend engineer' })
    expect(screen.getByText('I am a backend engineer')).toBeInTheDocument()
    expect(screen.getByLabelText('Your answer')).toBeDisabled()

    ws.push({ type: 'thinking' })
    ws.push({ type: 'token', text: 'How do ' })
    ws.push({ type: 'token', text: 'you test?' })
    expect(screen.getByRole('status')).toHaveTextContent('How do you test?')
    ws.push(question('q2', 2, 'How do you test your APIs?', { ack: 'Thanks, let\'s move on.' }))
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
    expect(screen.getByText('How do you test your APIs?')).toBeInTheDocument()
    expect(screen.getByText("Thanks, let's move on.")).toBeInTheDocument()
    expect(screen.getByLabelText('Your answer')).toBeEnabled()
  })

  it('restores the transcript after a reload and does not duplicate the replayed question', () => {
    const ws = setup()
    ws.push({
      ...emptyState, status: 'in_progress', main_asked: 2,
      turns: [
        { question_id: 'q1', order_no: 1, topic: 'T', ack: '', text: 'First question?', is_follow_up: false, answer: 'First answer' },
        { question_id: 'q2', order_no: 2, topic: 'T', ack: '', text: 'Second question?', is_follow_up: false, answer: null },
      ],
    })
    expect(screen.getByText('First answer')).toBeInTheDocument()
    ws.push(question('q2', 2, 'Second question?', { replay: true }))
    expect(screen.getAllByText('Second question?')).toHaveLength(1)
    expect(screen.getByLabelText('Your answer')).toBeEnabled()
  })

  it('does not allow sending an empty answer', async () => {
    const ws = setup()
    ws.push(emptyState)
    ws.push(question('q1', 1, 'Intro?'))
    expect(screen.getByRole('button', { name: 'Send answer' })).toBeDisabled()
    await userEvent.type(screen.getByLabelText('Your answer'), '   ')
    expect(screen.getByRole('button', { name: 'Send answer' })).toBeDisabled()
  })

  it('shows a retryable error and resumes with start', async () => {
    const ws = setup()
    ws.push(emptyState)
    ws.push({ type: 'error', message: 'Cannot reach Ollama', retryable: true })
    expect(screen.getByRole('alert')).toHaveTextContent('Cannot reach Ollama')
    await userEvent.click(screen.getByRole('button', { name: 'Try again' }))
    expect(ws.sent.at(-1)).toEqual({ type: 'start' })
  })

  it('shows completion without an answer box', () => {
    const ws = setup()
    ws.push(emptyState)
    ws.push({ type: 'complete', message: 'done' })
    expect(screen.getByText('Interview complete.')).toBeInTheDocument()
    expect(screen.queryByLabelText('Your answer')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'End interview' })).not.toBeInTheDocument()
  })

  it('offers a generate-report button after the interview and never starts a report by itself', async () => {
    const calls: Array<[string, string | undefined]> = []
    vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
      calls.push([String(url), init?.method])
      if (init?.method === 'POST') return new Response(JSON.stringify({ status: 'running' }), { status: 202 })
      return new Response(JSON.stringify({ detail: 'none' }), { status: 404 })
    }))
    const ws = setup()
    ws.push(emptyState)
    ws.push({ type: 'complete', message: 'done' })
    expect(calls).toEqual([])
    await userEvent.click(screen.getByRole('button', { name: 'Generate feedback report' }))
    await waitFor(() => expect(calls.some(([u, m]) => u.endsWith('/sessions/s1/report') && m === 'POST')).toBe(true))
  })

  it('shows why a report could not be started', async () => {
    vi.stubGlobal('fetch', vi.fn(async (_u: string, init?: RequestInit) =>
      init?.method === 'POST'
        ? new Response(JSON.stringify({ detail: 'Answer at least one question' }), { status: 409 })
        : new Response('{}', { status: 404 })))
    const ws = setup()
    ws.push({ ...emptyState, status: 'completed' })
    await userEvent.click(screen.getByRole('button', { name: 'Generate feedback report' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Answer at least one question')
  })

  it('opens a completed interview straight to the finished state', () => {
    const ws = setup()
    ws.push({ ...emptyState, status: 'completed' })
    expect(screen.getByText('Interview complete.')).toBeInTheDocument()
    expect(ws.sent).toEqual([])
  })

  it('offers reconnect when the connection drops', async () => {
    const ws = setup()
    ws.push(emptyState)
    act(() => ws.onclose?.())
    expect(screen.getByRole('alert')).toHaveTextContent('Connection lost')
    await userEvent.click(screen.getByRole('button', { name: 'Reconnect' }))
    expect(MockSocket.instances).toHaveLength(2)
  })

  it('ends the interview after confirmation', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    const ws = setup()
    ws.push(emptyState)
    ws.push(question('q1', 1, 'Intro?'))
    await userEvent.click(screen.getByRole('button', { name: 'End interview' }))
    expect(ws.sent.at(-1)).toEqual({ type: 'end' })
  })
})
