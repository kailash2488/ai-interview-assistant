import { Loader2, Mic, Square, Volume2, VolumeX } from 'lucide-react'
import type { useVoice } from '../lib/useVoice'
import { cn } from '../lib/utils'
import { Button } from './ui/button'

type Voice = ReturnType<typeof useVoice>

const mmss = (s: number) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`

/** Mic button, level meter and status for answering by voice. Only shown while voice mode is on. */
export function VoicePanel({ voice, canAnswer, lastQuestion }: { voice: Voice; canAnswer: boolean; lastQuestion: string | null }) {
  if (!voice.status) return <p className="text-sm text-slate-500">Checking voice…</p>

  if (!voice.canListen) {
    return (
      <div role="status" className="rounded-xl bg-amber-50 p-3.5 text-sm text-amber-900">
        <strong className="font-semibold">Voice answers are not set up on this server.</strong>{' '}
        {voice.status.stt.hint ?? 'This browser cannot record audio.'} You can still type your answers
        {voice.canSpeak ? ', and questions can be read aloud.' : '.'}
      </div>
    )
  }

  const recording = voice.rec === 'recording'
  const busy = voice.rec === 'transcribing'
  const bars = [0.12, 0.25, 0.4, 0.6, 0.85]

  return (
    <div className="space-y-3 rounded-2xl border border-brand-200 bg-brand-50/50 p-4">
      <div className="flex flex-wrap items-center gap-4">
        {recording ? (
          <button type="button" onClick={voice.stopRecording} aria-label="Stop recording" className="relative flex size-14 items-center justify-center rounded-full bg-red-600 text-white shadow-lg ring-4 ring-red-200 transition-transform hover:scale-105 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-red-600">
            <Square className="size-5 fill-current" aria-hidden />
          </button>
        ) : (
          <button
            type="button"
            onClick={voice.startRecording}
            disabled={!canAnswer || busy}
            aria-label="Record answer"
            className="flex size-14 items-center justify-center rounded-full bg-gradient-to-b from-brand-500 to-brand-700 text-white shadow-glow transition-transform hover:scale-105 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-600 disabled:cursor-not-allowed disabled:from-slate-300 disabled:to-slate-300 disabled:shadow-none disabled:hover:scale-100"
          >
            {busy ? <Loader2 className="size-6 animate-spin" aria-hidden /> : <Mic className="size-6" aria-hidden />}
          </button>
        )}

        <div className="min-w-0 flex-1" aria-live="polite">
          {recording && (
            <div className="flex items-center gap-3">
              <span aria-hidden className="flex h-6 items-end gap-1">
                {bars.map((b, i) => (
                  <span key={i} className={cn('w-1.5 rounded-full transition-all', voice.level / 0.25 >= b ? 'bg-red-500' : 'bg-red-200')} style={{ height: `${30 + b * 70}%` }} />
                ))}
              </span>
              <span className="text-sm font-medium text-slate-800">Recording… {mmss(voice.seconds)}</span>
            </div>
          )}
          {busy && <p className="text-sm font-medium text-slate-800">Transcribing your answer…</p>}
          {!recording && !busy && (
            <p className="text-sm text-slate-600">{canAnswer ? 'Press the microphone and speak your answer. You can edit the text before sending.' : 'Wait for the next question.'}</p>
          )}
          {recording && <p className="mt-0.5 text-xs text-slate-500">{voice.autoStop ? 'Stops by itself when you stop talking, or press the square.' : 'Press the square when you are done.'}</p>}
        </div>

        <div className="flex items-center gap-2">
          {voice.speaking ? (
            <Button type="button" variant="secondary" size="sm" onClick={voice.stopSpeaking}>
              <VolumeX className="size-4" aria-hidden /> Stop audio
            </Button>
          ) : (
            lastQuestion &&
            voice.canSpeak && (
              <Button type="button" variant="secondary" size="sm" onClick={() => voice.speak(lastQuestion)} disabled={recording || busy}>
                <Volume2 className="size-4" aria-hidden /> Replay question
              </Button>
            )
          )}
        </div>
      </div>

      <label className="flex items-center gap-2 text-xs text-slate-600">
        <input type="checkbox" checked={voice.autoStop} onChange={(e) => voice.setAutoStop(e.target.checked)} className="accent-brand-600" />
        Stop automatically when I stop talking
      </label>

      {voice.error && (
        <p role="alert" className="text-sm text-red-700">
          {voice.error}
        </p>
      )}
    </div>
  )
}
