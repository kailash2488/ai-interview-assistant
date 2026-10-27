import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { AudioRecorder, MicError, SPEECH_LEVEL, SilenceDetector, type RecorderDeps, type StopReason } from './recorder'

describe('SilenceDetector', () => {
  const LOUD = SPEECH_LEVEL * 3
  it('never stops before any speech was heard', () => {
    const d = new SilenceDetector(1000)
    for (let t = 0; t <= 10_000; t += 100) expect(d.feed(0, t)).toBe(false)
    expect(d.heardSpeech).toBe(false)
  })

  it('ignores a short click, then waits for real speech', () => {
    const d = new SilenceDetector(1000)
    d.feed(LOUD, 0)
    d.feed(LOUD, 100) // 100 ms of noise only
    for (let t = 200; t <= 3000; t += 100) expect(d.feed(0, t)).toBe(false)
    expect(d.heardSpeech).toBe(false)
  })

  it('stops after speech followed by the configured silence', () => {
    const d = new SilenceDetector(1000)
    let t = 0
    for (; t <= 2000; t += 100) d.feed(LOUD, t)
    expect(d.heardSpeech).toBe(true)
    const results: boolean[] = []
    for (t += 100; t <= 3300; t += 100) results.push(d.feed(0, t))
    // quiet is counted from the last loud tick (t = 2000), so 1000 ms is reached at t = 3000, the ninth call after the loop's skipped tick
    expect(results.indexOf(true)).toBe(8)
    expect(results.slice(0, 8).every((r) => !r)).toBe(true)
  })

  it('a pause shorter than the limit does not stop it, and speech resets the quiet timer', () => {
    const d = new SilenceDetector(1000)
    let t = 0
    for (; t <= 1000; t += 100) d.feed(LOUD, t)
    for (let i = 0; i < 8; i++, t += 100) expect(d.feed(0, t)).toBe(false) // 800 ms of quiet
    d.feed(LOUD, t); t += 100 // talking again
    for (let i = 0; i < 8; i++, t += 100) expect(d.feed(0, t)).toBe(false)
  })
})

class FakeTrack {
  stopped = false
  stop() {
    this.stopped = true
  }
}

function setup(opts: { silenceMs?: number | null; maxMs?: number; level?: { value: number }; failWith?: { name: string } } = {}) {
  const level = opts.level ?? { value: 0 }
  const track = new FakeTrack()
  const clock = { t: 0 }
  const created: { recorder?: FakeMediaRecorder; ctxClosed: boolean } = { ctxClosed: false }

  class FakeMediaRecorder {
    state: 'inactive' | 'recording' = 'inactive'
    mimeType = 'audio/webm'
    ondataavailable: ((e: { data: Blob }) => void) | null = null
    onstop: (() => void) | null = null
    constructor() {
      created.recorder = this
    }
    start() {
      this.state = 'recording'
      this.ondataavailable?.({ data: new Blob(['x'.repeat(3000)]) })
    }
    stop() {
      this.state = 'inactive'
      this.onstop?.()
    }
  }
  class FakeAudioContext {
    createAnalyser() {
      return {
        fftSize: 1024,
        getByteTimeDomainData: (buf: Uint8Array) => buf.fill(Math.round(128 + level.value * 128)),
      }
    }
    createMediaStreamSource() {
      return { connect: () => undefined }
    }
    close() {
      created.ctxClosed = true
      return Promise.resolve()
    }
  }
  const deps: RecorderDeps = {
    getUserMedia: opts.failWith ? () => Promise.reject(opts.failWith) : () => Promise.resolve({ getTracks: () => [track] } as unknown as MediaStream),
    MediaRecorderCtor: FakeMediaRecorder as unknown as typeof MediaRecorder,
    AudioContextCtor: FakeAudioContext as unknown as typeof AudioContext,
    now: () => clock.t,
  }
  const finished: Array<{ blob: Blob; reason: StopReason; ms: number }> = []
  const levels: number[] = []
  const rec = new AudioRecorder({
    silenceMs: opts.silenceMs === undefined ? 1000 : opts.silenceMs,
    maxMs: opts.maxMs,
    tickMs: 100,
    deps,
    onLevel: (l) => levels.push(l),
    onFinish: (blob, reason, ms) => finished.push({ blob, reason, ms }),
  })
  const advance = (ms: number) => {
    for (let i = 0; i < ms / 100; i++) {
      clock.t += 100
      vi.advanceTimersByTime(100)
    }
  }
  return { rec, track, finished, levels, level, advance, created }
}

describe('AudioRecorder', () => {
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => vi.useRealTimers())

  it('records, reports levels and finishes on a manual stop, releasing the microphone', async () => {
    const s = setup()
    await s.rec.start()
    expect(s.rec.recording).toBe(true)
    s.level.value = 0.2
    s.advance(500)
    expect(s.levels.length).toBe(5)
    expect(s.levels[0]).toBeCloseTo(0.2, 1)
    s.rec.stop()
    expect(s.finished).toHaveLength(1)
    expect(s.finished[0].reason).toBe('manual')
    expect(s.finished[0].blob.size).toBeGreaterThan(1000)
    expect(s.track.stopped).toBe(true)
    expect(s.created.ctxClosed).toBe(true)
    s.rec.stop() // stopping twice does nothing
    expect(s.finished).toHaveLength(1)
  })

  it('stops by itself after the speaker goes quiet', async () => {
    const s = setup({ silenceMs: 1000 })
    await s.rec.start()
    s.level.value = 0.3
    s.advance(1500)
    s.level.value = 0
    s.advance(1500)
    expect(s.finished).toHaveLength(1)
    expect(s.finished[0].reason).toBe('silence')
    expect(s.finished[0].ms).toBeGreaterThanOrEqual(2500)
  })

  it('does not stop on silence when automatic stopping is off', async () => {
    const s = setup({ silenceMs: null })
    await s.rec.start()
    s.level.value = 0.3
    s.advance(1000)
    s.level.value = 0
    s.advance(10_000)
    expect(s.finished).toHaveLength(0)
    expect(s.rec.recording).toBe(true)
    s.rec.stop()
    expect(s.finished[0].reason).toBe('manual')
  })

  it('stops at the maximum length', async () => {
    const s = setup({ silenceMs: null, maxMs: 3000 })
    await s.rec.start()
    s.advance(3500)
    expect(s.finished).toHaveLength(1)
    expect(s.finished[0].reason).toBe('max')
  })

  it('cancel throws the recording away and still releases the microphone', async () => {
    const s = setup()
    await s.rec.start()
    s.advance(300)
    s.rec.cancel()
    expect(s.finished).toHaveLength(0)
    expect(s.track.stopped).toBe(true)
  })

  it.each([
    ['NotAllowedError', /blocked/],
    ['NotFoundError', /No microphone/],
    ['AbortError', /could not be started/],
  ])('turns a %s into a message the user can act on', async (name, pattern) => {
    const s = setup({ failWith: { name } })
    await expect(s.rec.start()).rejects.toBeInstanceOf(MicError)
    await expect(s.rec.start()).rejects.toThrow(pattern)
    expect(s.rec.recording).toBe(false)
  })
})
