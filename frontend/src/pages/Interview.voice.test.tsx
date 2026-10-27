import { act, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { ServerMessage } from '../lib/api'
import { Interview } from './Interview'

const h = vi.hoisted(() => ({
  spoken: [] as string[],
  cancelledRecordings: 0,
  startError: null as string | null,
  blobSize: 4000,
  recorder: null as null | { finish: () => void },
}))

vi.mock('../lib/recorder', () => {
  class MicError extends Error {}
  class AudioRecorder {
    opts: { onFinish: (b: Blob, r: string, ms: number) => void }
    constructor(opts: AudioRecorder['opts']) {
      this.opts = opts
      h.recorder = { finish: () => opts.onFinish(new Blob(['x'.repeat(h.blobSize)]), 'manual', 5000) }
    }
    async start() {
      if (h.startError) throw new MicError(h.startError)
    }
    stop() {
      h.recorder?.finish()
    }
    cancel() {
      h.cancelledRecordings++
    }
  }
  return { AudioRecorder, MicError, recordingSupported: () => true, SilenceDetector: class {}, SPEECH_LEVEL: 0.04 }
})
vi.mock('../lib/speech', () => {
  class Speaker {
    static browserAvailable = () => true
    speak = vi.fn(async (t: string) => {
      h.spoken.push(t)
    })
    cancel = vi.fn()
  }
  return { Speaker }
})

class MockSocket {
  static instances: MockSocket[] = []
  sent: Array<Record<string, unknown>> = []
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
  push(msg: ServerMessage | Record<string, unknown>) {
    act(() => this.onmessage?.({ data: JSON.stringify(msg) }))
  }
}

const question = (id: string, no: number, text: string, extra: object = {}) => ({
  type: 'question' as const, question_id: id, order_no: no, topic: 'T', text, ack: '', is_follow_up: false, replay: false, progress: { main_asked: no, main_total: 8 }, ...extra,
})
const stateMsg = { type: 'state' as const, session_id: 's1', status: 'planned', main_total: 8, main_asked: 0, turns: [] }

let status: { stt: { available: boolean; hint: string | null }; tts: { available: boolean } }
let transcribeResponse: { status: number; body: unknown }
let uploads: FormData[]

beforeEach(() => {
  h.spoken = []
  h.cancelledRecordings = 0
  h.startError = null
  h.blobSize = 4000
  h.recorder = null
  MockSocket.instances = []
  uploads = []
  localStorage.clear()
  status = { stt: { available: true, hint: null }, tts: { available: true } }
  transcribeResponse = { status: 200, body: { text: 'I used asyncio for IO bound work', seconds: 6, words: 7, wpm: 140, pauses: 1, longest_pause: 1.8, fillers: 0 } }
  vi.stubGlobal('WebSocket', MockSocket)
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
    const path = String(url).replace(/^\/api/, '')
    if (path === '/voice/status') return new Response(JSON.stringify({ stt: { model: 'base.en', loaded: false, ...status.stt }, tts: { voice: 'v', hint: null, ...status.tts } }))
    if (path === '/voice/transcribe') {
      uploads.push(init!.body as FormData)
      return new Response(JSON.stringify(transcribeResponse.body), { status: transcribeResponse.status })
    }
    return new Response('{}', { status: 404 })
  }))
})
afterEach(() => vi.unstubAllGlobals())

function setup() {
  render(
    <MemoryRouter initialEntries={['/sessions/s1/interview']}>
      <Routes>
        <Route path="sessions/:sessionId/interview" element={<Interview />} />
      </Routes>
    </MemoryRouter>,
  )
  return MockSocket.instances[0]
}

async function voiceOn() {
  await userEvent.click(screen.getByRole('switch', { name: 'Voice mode' }))
  return screen.findByRole('button', { name: 'Record answer' })
}

describe('voice mode in the interview room', () => {
  it('is off by default and does not touch the microphone or the voice server', async () => {
    const ws = setup()
    ws.push(stateMsg)
    ws.push(question('q1', 1, 'Tell me about yourself?'))
    expect(screen.getByRole('switch', { name: 'Voice mode' })).toHaveAttribute('aria-checked', 'false')
    expect(screen.queryByRole('button', { name: 'Record answer' })).not.toBeInTheDocument()
    expect(h.spoken).toEqual([])
    expect(vi.mocked(fetch).mock.calls.some(([u]) => String(u).includes('/voice/'))).toBe(false)
  })

  it('turns on, checks what the server offers, and remembers the choice', async () => {
    const ws = setup()
    ws.push(stateMsg)
    ws.push(question('q1', 1, 'Tell me about yourself?'))
    expect(await voiceOn()).toBeEnabled()
    expect(screen.getByRole('switch', { name: 'Voice mode' })).toHaveAttribute('aria-checked', 'true')
    expect(localStorage.getItem('aia.voice')).toBe('1')
    await userEvent.click(screen.getByRole('switch', { name: 'Voice mode' }))
    expect(localStorage.getItem('aia.voice')).toBe('0')
    expect(screen.queryByRole('button', { name: 'Record answer' })).not.toBeInTheDocument()
  })

  it('reads new questions aloud (with the short acknowledgement) but not one replayed after a reload', async () => {
    localStorage.setItem('aia.voice', '1')
    const ws = setup()
    await screen.findByRole('button', { name: 'Record answer' })
    ws.push(stateMsg)
    ws.push(question('q1', 1, 'First question?', { replay: true }))
    expect(h.spoken).toEqual([])
    ws.push(question('q2', 2, 'Second question?', { ack: 'Thanks, let\'s move on.' }))
    await waitFor(() => expect(h.spoken).toEqual(["Thanks, let's move on. Second question?"]))
  })

  it('does not speak when voice mode is off', async () => {
    const ws = setup()
    ws.push(stateMsg)
    ws.push(question('q1', 1, 'Silent question?'))
    await new Promise((r) => setTimeout(r, 20))
    expect(h.spoken).toEqual([])
  })

  it('records, transcribes with the interview id, fills the box and sends the measurements with the answer', async () => {
    const ws = setup()
    ws.push(stateMsg)
    ws.push(question('q1', 1, 'How do you use asyncio?'))
    await userEvent.click(await voiceOn())
    expect(await screen.findByRole('button', { name: 'Stop recording' })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Stop recording' }))
    expect(await screen.findByDisplayValue('I used asyncio for IO bound work')).toBeInTheDocument()
    expect(uploads[0].get('session_id')).toBe('s1')
    expect((uploads[0].get('file') as File).size).toBe(4000)

    await userEvent.click(screen.getByRole('button', { name: 'Send answer' }))
    expect(ws.sent.at(-1)).toEqual({ type: 'answer', text: 'I used asyncio for IO bound work', voice: { seconds: 6, words: 7, wpm: 140, pauses: 1, longest_pause: 1.8, fillers: 0 } })

    ws.push(question('q2', 2, 'Next?'))
    await userEvent.type(screen.getByLabelText('Your answer'), 'typed answer')
    await userEvent.click(screen.getByRole('button', { name: 'Send answer' }))
    expect(ws.sent.at(-1)).toEqual({ type: 'answer', text: 'typed answer' }) // measurements belong to one recording only
  })

  it('appends a transcript to what was already typed', async () => {
    const ws = setup()
    ws.push(stateMsg)
    ws.push(question('q1', 1, 'Q?'))
    await voiceOn()
    await userEvent.type(screen.getByLabelText('Your answer'), 'Short intro.')
    await userEvent.click(screen.getByRole('button', { name: 'Record answer' }))
    await userEvent.click(await screen.findByRole('button', { name: 'Stop recording' }))
    expect(await screen.findByDisplayValue('Short intro. I used asyncio for IO bound work')).toBeInTheDocument()
  })

  it('explains a blocked microphone and lets the user try again', async () => {
    h.startError = "Microphone access is blocked. Allow it in your browser's address bar, then try again."
    const ws = setup()
    ws.push(stateMsg)
    ws.push(question('q1', 1, 'Q?'))
    await userEvent.click(await voiceOn())
    await userEvent.click(screen.getByRole('button', { name: 'Record answer' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Microphone access is blocked')
    expect(screen.getByRole('button', { name: 'Record answer' })).toBeEnabled()
  })

  it('shows why a recording could not be transcribed', async () => {
    transcribeResponse = { status: 422, body: { detail: 'No speech was heard. Check your microphone and try again.' } }
    const ws = setup()
    ws.push(stateMsg)
    ws.push(question('q1', 1, 'Q?'))
    await voiceOn()
    await userEvent.click(screen.getByRole('button', { name: 'Record answer' }))
    await userEvent.click(await screen.findByRole('button', { name: 'Stop recording' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('No speech was heard')
    expect(screen.getByLabelText('Your answer')).toHaveValue('')
  })

  it('ignores a recording that is far too short without calling the server', async () => {
    h.blobSize = 200
    const ws = setup()
    ws.push(stateMsg)
    ws.push(question('q1', 1, 'Q?'))
    await voiceOn()
    await userEvent.click(screen.getByRole('button', { name: 'Record answer' }))
    await userEvent.click(await screen.findByRole('button', { name: 'Stop recording' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('too short')
    expect(uploads).toHaveLength(0)
  })

  it('says plainly when the server has no speech recognition, and still reads questions aloud', async () => {
    status = { stt: { available: false, hint: 'Install the voice extras: pip install ".[voice]"' }, tts: { available: false } }
    const ws = setup()
    ws.push(stateMsg)
    await userEvent.click(screen.getByRole('switch', { name: 'Voice mode' }))
    expect(await screen.findByText(/Voice answers are not set up on this server/)).toBeInTheDocument()
    expect(screen.getByText(/pip install/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Record answer' })).not.toBeInTheDocument()
    expect(screen.getByText(/questions can be read aloud/)).toBeInTheDocument() // the browser voice still works
    ws.push(question('q1', 1, 'Spoken by the browser?'))
    await waitFor(() => expect(h.spoken).toEqual(['Spoken by the browser?']))
  })

  it('cannot record while the next question is being prepared', async () => {
    const ws = setup()
    ws.push(stateMsg)
    ws.push(question('q1', 1, 'Q?'))
    await userEvent.click(await voiceOn())
    await userEvent.type(screen.getByLabelText('Your answer'), 'my answer')
    await userEvent.click(screen.getByRole('button', { name: 'Send answer' }))
    expect(screen.getByRole('button', { name: 'Record answer' })).toBeDisabled()
    expect(screen.getByText('Wait for the next question.')).toBeInTheDocument()
  })

  it('stops a recording that is still running when the answer is sent', async () => {
    const ws = setup()
    ws.push(stateMsg)
    ws.push(question('q1', 1, 'Q?'))
    await voiceOn()
    await userEvent.click(screen.getByRole('button', { name: 'Record answer' }))
    await screen.findByRole('button', { name: 'Stop recording' })
    await userEvent.type(screen.getByLabelText('Your answer'), 'I will just type this')
    expect(h.cancelledRecordings).toBe(0)
    await userEvent.click(screen.getByRole('button', { name: 'Send answer' }))
    expect(h.cancelledRecordings).toBe(1)
    expect(ws.sent.at(-1)).toEqual({ type: 'answer', text: 'I will just type this' })
    expect(screen.queryByRole('button', { name: 'Stop recording' })).not.toBeInTheDocument()
  })

  it('stops a recording when voice mode is switched off', async () => {
    const ws = setup()
    ws.push(stateMsg)
    ws.push(question('q1', 1, 'Q?'))
    await voiceOn()
    await userEvent.click(screen.getByRole('button', { name: 'Record answer' }))
    await screen.findByRole('button', { name: 'Stop recording' })
    await userEvent.click(screen.getByRole('switch', { name: 'Voice mode' }))
    expect(h.cancelledRecordings).toBe(1)
    expect(screen.queryByRole('button', { name: 'Stop recording' })).not.toBeInTheDocument()
  })

  it('lets the user hear the question again', async () => {
    const ws = setup()
    ws.push(stateMsg)
    ws.push(question('q1', 1, 'Explain connection pooling?'))
    await voiceOn()
    await userEvent.click(await screen.findByRole('button', { name: /Replay question/ }))
    await waitFor(() => expect(h.spoken).toContain('Explain connection pooling?'))
  })

  it('lets the user turn off automatic stopping', async () => {
    const ws = setup()
    ws.push(stateMsg)
    ws.push(question('q1', 1, 'Q?'))
    await userEvent.click(await voiceOn())
    const box = screen.getByRole('checkbox', { name: /Stop automatically/ })
    expect(box).toBeChecked()
    await userEvent.click(box)
    expect(box).not.toBeChecked()
  })
})
