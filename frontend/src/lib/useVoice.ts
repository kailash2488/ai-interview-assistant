import { useCallback, useEffect, useRef, useState } from 'react'
import { api, type VoiceMetrics, type VoiceStatus } from './api'
import { AudioRecorder, MicError, recordingSupported } from './recorder'
import { Speaker } from './speech'

const KEY = 'aia.voice'
const SILENCE_MS = 2500
const MAX_MS = 4 * 60_000

export type RecState = 'idle' | 'recording' | 'transcribing'

/** Everything the interview room needs for voice: availability, speaking questions aloud and recording answers. */
export function useVoice(sessionId: string, onTranscript: (text: string, metrics: VoiceMetrics) => void) {
  const [enabled, setEnabled] = useState(() => localStorage.getItem(KEY) === '1')
  const [status, setStatus] = useState<VoiceStatus | null>(null)
  const [rec, setRec] = useState<RecState>('idle')
  const [level, setLevel] = useState(0)
  const [seconds, setSeconds] = useState(0)
  const [speaking, setSpeaking] = useState(false)
  const [autoStop, setAutoStop] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const recorder = useRef<AudioRecorder | null>(null)
  const speaker = useRef<Speaker | null>(null)
  const callback = useRef(onTranscript)
  callback.current = onTranscript

  const canListen = !!status?.stt.available && recordingSupported()
  const canSpeak = !!status?.tts.available || Speaker.browserAvailable()

  useEffect(() => {
    if (!enabled || status) return
    api.voiceStatus().then(setStatus).catch(() => setStatus({ stt: { available: false, model: '', loaded: false, hint: 'Voice is not available on this server.' }, tts: { available: false, voice: '', hint: null } }))
  }, [enabled, status])

  useEffect(() => {
    if (rec !== 'recording') return
    setSeconds(0)
    const t = setInterval(() => setSeconds((s) => s + 1), 1000)
    return () => clearInterval(t)
  }, [rec])

  useEffect(
    () => () => {
      recorder.current?.cancel()
      speaker.current?.cancel()
    },
    [],
  )

  const toggle = useCallback((on: boolean) => {
    setEnabled(on)
    localStorage.setItem(KEY, on ? '1' : '0')
    if (!on) {
      recorder.current?.cancel()
      speaker.current?.cancel()
      setRec('idle')
      setSpeaking(false)
    }
  }, [])

  const stopSpeaking = useCallback(() => {
    speaker.current?.cancel()
    setSpeaking(false)
  }, [])

  const speak = useCallback(
    async (text: string) => {
      if (!enabled || !canSpeak) return
      speaker.current ??= new Speaker(!!status?.tts.available)
      setSpeaking(true)
      try {
        await speaker.current.speak(text)
      } catch {
        setError('The question could not be read aloud. You can still read it on screen.')
      } finally {
        setSpeaking(false)
      }
    },
    [enabled, canSpeak, status],
  )

  const startRecording = useCallback(async () => {
    if (rec !== 'idle' || !canListen) return
    setError(null)
    stopSpeaking()
    recorder.current = new AudioRecorder({
      silenceMs: autoStop ? SILENCE_MS : null,
      maxMs: MAX_MS,
      onLevel: setLevel,
      onFinish: async (blob) => {
        setLevel(0)
        if (blob.size < 1500) {
          setRec('idle')
          setError('That recording was too short. Press the microphone and speak your answer.')
          return
        }
        setRec('transcribing')
        try {
          const t = await api.transcribe(blob, sessionId)
          callback.current(t.text, { seconds: t.seconds, words: t.words, wpm: t.wpm, pauses: t.pauses, longest_pause: t.longest_pause, fillers: t.fillers })
        } catch (e) {
          setError(e instanceof Error ? e.message : 'The recording could not be transcribed.')
        } finally {
          setRec('idle')
        }
      },
    })
    try {
      await recorder.current.start()
      setRec('recording')
    } catch (e) {
      setError(e instanceof MicError ? e.message : 'The microphone could not be started.')
      setRec('idle')
    }
  }, [rec, canListen, autoStop, sessionId, stopSpeaking])

  const stopRecording = useCallback(() => recorder.current?.stop('manual'), [])
  const cancelRecording = useCallback(() => {
    recorder.current?.cancel()
    setRec('idle')
    setLevel(0)
  }, [])

  return { enabled, toggle, status, canListen, canSpeak, rec, level, seconds, speaking, autoStop, setAutoStop, error, setError, speak, stopSpeaking, startRecording, stopRecording, cancelRecording }
}
