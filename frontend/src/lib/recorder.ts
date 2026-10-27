/** Microphone recording with automatic stop when the speaker goes quiet.
 *  The browser APIs are injected so the logic can be tested without a microphone. */

export type StopReason = 'manual' | 'silence' | 'max'

export const SPEECH_LEVEL = 0.04 // RMS (0 to 1) above which the microphone is picking up speech
const MIN_SPEECH_MS = 400 // speech must last this long before silence can end the recording (ignores clicks and coughs)

/** Decides when to stop: after some speech, then `silenceMs` of quiet. Feed it a level every tick. */
export class SilenceDetector {
  private speechMs = 0
  private quietMs = 0
  private last: number | null = null

  private readonly silenceMs: number
  private readonly threshold: number

  constructor(silenceMs: number, threshold = SPEECH_LEVEL) {
    this.silenceMs = silenceMs
    this.threshold = threshold
  }

  /** Returns true when the recording should stop. */
  feed(level: number, nowMs: number): boolean {
    const dt = this.last === null ? 0 : nowMs - this.last
    this.last = nowMs
    if (level >= this.threshold) {
      this.speechMs += dt
      this.quietMs = 0
      return false
    }
    if (this.speechMs < MIN_SPEECH_MS) return false
    this.quietMs += dt
    return this.quietMs >= this.silenceMs
  }

  get heardSpeech(): boolean {
    return this.speechMs >= MIN_SPEECH_MS
  }
}

export interface RecorderDeps {
  getUserMedia: (c: MediaStreamConstraints) => Promise<MediaStream>
  MediaRecorderCtor: typeof MediaRecorder
  AudioContextCtor: typeof AudioContext
  now: () => number
}

export interface RecorderOptions {
  silenceMs?: number | null // null: never stop automatically
  maxMs?: number
  tickMs?: number
  onLevel?: (level: number) => void
  onFinish: (blob: Blob, reason: StopReason, durationMs: number) => void
  deps?: RecorderDeps
}

export class MicError extends Error {}

function defaultDeps(): RecorderDeps {
  const AudioContextCtor = window.AudioContext ?? (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext
  return { getUserMedia: (c) => navigator.mediaDevices.getUserMedia(c), MediaRecorderCtor: window.MediaRecorder, AudioContextCtor, now: () => performance.now() }
}

export function recordingSupported(): boolean {
  return typeof navigator !== 'undefined' && !!navigator.mediaDevices?.getUserMedia && typeof window !== 'undefined' && typeof window.MediaRecorder !== 'undefined'
}

export class AudioRecorder {
  private stream: MediaStream | null = null
  private recorder: MediaRecorder | null = null
  private ctx: AudioContext | null = null
  private timer: ReturnType<typeof setInterval> | null = null
  private chunks: Blob[] = []
  private startedAt = 0
  private reason: StopReason = 'manual'
  private finished = false
  private cancelled = false
  private readonly deps: RecorderDeps
  private readonly silence: SilenceDetector | null

  private readonly opts: RecorderOptions

  constructor(opts: RecorderOptions) {
    this.opts = opts
    this.deps = opts.deps ?? defaultDeps()
    this.silence = opts.silenceMs ? new SilenceDetector(opts.silenceMs) : null
  }

  get recording(): boolean {
    return this.recorder?.state === 'recording'
  }

  async start(): Promise<void> {
    try {
      this.stream = await this.deps.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } })
    } catch (e) {
      const name = (e as { name?: string })?.name
      if (name === 'NotAllowedError' || name === 'SecurityError') throw new MicError("Microphone access is blocked. Allow it in your browser's address bar, then try again.")
      if (name === 'NotFoundError' || name === 'OverconstrainedError') throw new MicError('No microphone was found. Plug one in and try again.')
      throw new MicError('The microphone could not be started.')
    }
    const analyser = this.setupAnalyser(this.stream)
    this.recorder = new this.deps.MediaRecorderCtor(this.stream)
    this.recorder.ondataavailable = (e: BlobEvent) => e.data.size > 0 && this.chunks.push(e.data)
    this.recorder.onstop = () => this.finish()
    this.startedAt = this.deps.now()
    this.recorder.start(250)

    const buffer = analyser ? new Uint8Array(analyser.fftSize) : null
    this.timer = setInterval(() => {
      const now = this.deps.now()
      let level = 0
      if (analyser && buffer) {
        analyser.getByteTimeDomainData(buffer)
        let sum = 0
        for (const v of buffer) sum += ((v - 128) / 128) ** 2
        level = Math.sqrt(sum / buffer.length)
      }
      this.opts.onLevel?.(level)
      if (this.opts.maxMs && now - this.startedAt >= this.opts.maxMs) this.stop('max')
      else if (this.silence?.feed(level, now)) this.stop('silence')
    }, this.opts.tickMs ?? 100)
  }

  private setupAnalyser(stream: MediaStream): AnalyserNode | null {
    try {
      this.ctx = new this.deps.AudioContextCtor()
      const analyser = this.ctx.createAnalyser()
      analyser.fftSize = 1024
      this.ctx.createMediaStreamSource(stream).connect(analyser)
      return analyser
    } catch {
      return null // recording still works; only the level meter and silence detection are lost
    }
  }

  stop(reason: StopReason = 'manual'): void {
    if (!this.recorder || this.recorder.state === 'inactive') return
    this.reason = reason
    this.recorder.stop()
  }

  /** Throw the recording away (leaving the page, or the user cancelled). */
  cancel(): void {
    this.cancelled = true
    if (this.recorder && this.recorder.state !== 'inactive') this.recorder.stop()
    else this.release()
  }

  private finish() {
    if (this.finished) return
    this.finished = true
    const durationMs = this.deps.now() - this.startedAt
    const type = this.recorder?.mimeType || 'audio/webm'
    this.release()
    if (!this.cancelled) this.opts.onFinish(new Blob(this.chunks, { type }), this.reason, durationMs)
  }

  private release() {
    if (this.timer) clearInterval(this.timer)
    this.timer = null
    this.stream?.getTracks().forEach((t) => t.stop())
    this.stream = null
    void this.ctx?.close().catch(() => undefined)
    this.ctx = null
  }
}
