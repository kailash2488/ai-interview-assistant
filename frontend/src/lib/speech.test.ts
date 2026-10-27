import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { Speaker } from './speech'

class FakeAudio {
  static instances: FakeAudio[] = []
  onended: (() => void) | null = null
  onpause: (() => void) | null = null
  onerror: (() => void) | null = null
  paused = false
  src: string
  constructor(src: string) {
    this.src = src
    FakeAudio.instances.push(this)
  }
  play() {
    return Promise.resolve()
  }
  pause() {
    this.paused = true
    this.onpause?.()
  }
}

let spoken: string[]
let cancelled: number

beforeEach(() => {
  FakeAudio.instances = []
  spoken = []
  cancelled = 0
  vi.stubGlobal('Audio', FakeAudio)
  vi.stubGlobal('URL', { createObjectURL: () => 'blob:fake', revokeObjectURL: () => undefined })
  class Utterance {
    voice: unknown = null
    rate = 1
    onend: (() => void) | null = null
    onerror: (() => void) | null = null
    text: string
    constructor(text: string) {
      this.text = text
    }
  }
  vi.stubGlobal('SpeechSynthesisUtterance', Utterance)
  Object.defineProperty(window, 'speechSynthesis', {
    configurable: true,
    value: {
      getVoices: () => [{ lang: 'de-DE', localService: true }, { lang: 'en-GB', localService: false }, { lang: 'en-US', localService: true }],
      speak: (u: { text: string; voice: { lang: string }; onend: () => void }) => {
        spoken.push(`${u.text}|${u.voice?.lang}`)
        u.onend()
      },
      cancel: () => cancelled++,
    },
  })
})
afterEach(() => vi.unstubAllGlobals())

// jsdom's Blob has no stream(), which a real Response needs, so a small stand-in is used
const audioResponse = () => ({ ok: true, status: 200, blob: async () => new Blob(['RIFFwav']) }) as unknown as Response
const ok = () => vi.fn(async () => audioResponse())

describe('Speaker', () => {
  it('plays the server voice and resolves when it ends', async () => {
    const fetchFn = ok()
    vi.stubGlobal('fetch', fetchFn)
    const done = new Speaker(true).speak('Tell me about yourself.')
    await vi.waitFor(() => expect(FakeAudio.instances).toHaveLength(1))
    FakeAudio.instances[0].onended?.()
    await done
    const [url, init] = fetchFn.mock.calls[0] as unknown as [string, RequestInit]
    expect(url).toMatch(/\/voice\/speak$/)
    expect(init.credentials).toBe('include')
    expect(JSON.parse(init.body as string)).toEqual({ text: 'Tell me about yourself.' })
    expect(spoken).toEqual([]) // the browser voice was not used
  })

  it('falls back to a local browser voice (preferring English on the device) when the server voice fails', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response('{}', { status: 503 })))
    await new Speaker(true).speak('Hello there')
    expect(spoken).toEqual(['Hello there|en-US'])
  })

  it('uses the browser voice directly when the server has none', async () => {
    const fetchFn = vi.fn()
    vi.stubGlobal('fetch', fetchFn)
    await new Speaker(false).speak('Hi')
    expect(fetchFn).not.toHaveBeenCalled()
    expect(spoken).toEqual(['Hi|en-US'])
  })

  it('rejects only when neither voice can be used', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response('{}', { status: 503 })))
    // @ts-expect-error simulate a browser without speech synthesis
    delete window.speechSynthesis
    vi.stubGlobal('SpeechSynthesisUtterance', undefined)
    await expect(new Speaker(true).speak('Hi')).rejects.toThrow(/speech request failed/)
  })

  it('cancel stops audio that is playing and lets the promise finish', async () => {
    vi.stubGlobal('fetch', ok())
    const speaker = new Speaker(true)
    const done = speaker.speak('A long question')
    await vi.waitFor(() => expect(FakeAudio.instances).toHaveLength(1))
    speaker.cancel()
    await done
    expect(FakeAudio.instances[0].paused).toBe(true)
    expect(cancelled).toBeGreaterThan(0)
  })

  it('a newer question replaces an older one that is still being fetched', async () => {
    let release!: () => void
    const gate = new Promise<void>((r) => (release = r))
    const fetchFn = vi.fn(async () => {
      await gate
      return audioResponse()
    })
    vi.stubGlobal('fetch', fetchFn)
    const speaker = new Speaker(true)
    const first = speaker.speak('First')
    const second = speaker.speak('Second')
    release()
    await vi.waitFor(() => expect(FakeAudio.instances.length).toBeGreaterThan(0))
    FakeAudio.instances.forEach((a) => a.onended?.())
    await Promise.all([first, second])
    expect(FakeAudio.instances).toHaveLength(1) // only the latest question was played
  })
})
