import { speakUrl } from './api'

/** Reads text aloud. Uses the server's local Piper voice when available, otherwise the browser's own voices
 *  (which also run on the device). Both can be interrupted. */
export class Speaker {
  private audio: HTMLAudioElement | null = null
  private url: string | null = null
  private token = 0

  private readonly useServer: boolean

  constructor(useServer: boolean) {
    this.useServer = useServer
  }

  static browserAvailable(): boolean {
    return typeof window !== 'undefined' && 'speechSynthesis' in window && typeof SpeechSynthesisUtterance !== 'undefined'
  }

  /** Resolves when the speech has finished or was cancelled. Rejects only when nothing could be played. */
  async speak(text: string): Promise<void> {
    this.cancel()
    const mine = ++this.token
    if (this.useServer) {
      try {
        const res = await fetch(speakUrl(), { method: 'POST', credentials: 'include', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text }) })
        if (!res.ok) throw new Error(`speech request failed (${res.status})`)
        const blob = await res.blob()
        if (mine !== this.token) return // cancelled while the audio was being made
        return await this.play(URL.createObjectURL(blob), mine)
      } catch (e) {
        if (!Speaker.browserAvailable()) throw e
        // fall through to the browser voice
      }
    }
    if (mine !== this.token) return
    return this.browserSpeak(text, mine)
  }

  private play(url: string, mine: number): Promise<void> {
    this.url = url
    const audio = new Audio(url)
    this.audio = audio
    return new Promise<void>((resolve, reject) => {
      const done = () => {
        if (this.audio === audio) this.cleanup()
        resolve()
      }
      audio.onended = done
      audio.onpause = () => mine !== this.token && done()
      audio.onerror = () => {
        this.cleanup()
        reject(new Error('The audio could not be played'))
      }
      audio.play().catch((e) => {
        this.cleanup()
        reject(e)
      })
    })
  }

  private browserSpeak(text: string, mine: number): Promise<void> {
    return new Promise<void>((resolve) => {
      const utterance = new SpeechSynthesisUtterance(text)
      const voices = window.speechSynthesis.getVoices()
      utterance.voice = voices.find((v) => v.lang.toLowerCase().startsWith('en') && v.localService) ?? voices.find((v) => v.lang.toLowerCase().startsWith('en')) ?? null
      utterance.rate = 1
      const end = () => resolve()
      utterance.onend = end
      utterance.onerror = end
      if (mine !== this.token) return resolve()
      window.speechSynthesis.speak(utterance)
    })
  }

  cancel(): void {
    this.token++
    if (this.audio) {
      this.audio.pause()
      this.cleanup()
    }
    if (Speaker.browserAvailable()) window.speechSynthesis.cancel()
  }

  private cleanup() {
    if (this.url) URL.revokeObjectURL(this.url)
    this.url = null
    this.audio = null
  }
}
