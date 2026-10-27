import { Briefcase, FileText, Paperclip, Upload } from 'lucide-react'
import { useRef, useState, type DragEvent } from 'react'
import { api, type DocumentItem, type DocumentKind } from '../lib/api'
import { ACCEPTED_EXTENSIONS, MAX_UPLOAD_MB, validateFile } from '../lib/files'
import { cn } from '../lib/utils'
import { DocumentRow } from './DocumentRow'
import { Button } from './ui/button'
import { Card } from './ui/card'
import { Textarea } from './ui/field'

interface Props {
  sessionId: string
  kind: DocumentKind
  title: string
  description: string
  required?: boolean
  multiple?: boolean
  allowPaste?: boolean
  documents: DocumentItem[]
  onChanged: () => void
}

export function DocumentSlot({ sessionId, kind, title, description, required, multiple, allowPaste, documents, onChanged }: Props) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [pasting, setPasting] = useState(false)
  const [pasted, setPasted] = useState('')

  async function uploadFiles(files: File[]) {
    setError(null)
    const chosen = multiple ? files : files.slice(0, 1)
    const problems = chosen.map(validateFile).filter((p): p is string => p !== null)
    if (problems.length) {
      setError(problems.join('\n'))
      return
    }
    setBusy(true)
    try {
      for (const file of chosen) await api.uploadDocument(sessionId, kind, file)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Upload failed')
    } finally {
      setBusy(false)
      onChanged()
    }
  }

  function onDrop(e: DragEvent) {
    e.preventDefault()
    setDragging(false)
    void uploadFiles(Array.from(e.dataTransfer.files))
  }

  async function submitPasted() {
    await uploadFiles([new File([pasted], `${kind}-pasted.txt`, { type: 'text/plain' })])
    setPasted('')
    setPasting(false)
  }

  async function remove(doc: DocumentItem) {
    try {
      await api.deleteDocument(sessionId, doc.id)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not remove file')
    }
    onChanged()
  }

  return (
    <Card className="space-y-4">
      <div className="flex items-start gap-4">
        <span className="flex size-11 shrink-0 items-center justify-center rounded-xl bg-brand-50 text-brand-600">
          {kind === 'resume' ? <FileText className="size-5" aria-hidden /> : kind === 'jd' ? <Briefcase className="size-5" aria-hidden /> : <Paperclip className="size-5" aria-hidden />}
        </span>
        <div>
          <h2 className="text-base font-semibold text-slate-900">
            {title} {required && <span className="ml-1 rounded-full bg-red-50 px-2 py-0.5 align-middle text-xs font-medium text-red-600">required</span>}
          </h2>
          <p className="text-sm text-slate-500">{description}</p>
        </div>
      </div>

      <div
        onDragOver={(e) => {
          e.preventDefault()
          setDragging(true)
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        className={cn(
          'flex flex-col items-center gap-2 rounded-2xl border-2 border-dashed px-4 py-7 text-center transition-colors',
          dragging ? 'border-brand-500 bg-brand-50' : 'border-slate-200 bg-slate-50/60 hover:border-brand-300 hover:bg-brand-50/40',
        )}
      >
        <span className="flex size-10 items-center justify-center rounded-full bg-white shadow-sm ring-1 ring-slate-200"><Upload className="size-5 text-brand-500" aria-hidden /></span>
        <p className="text-sm text-slate-600">
          Drag &amp; drop {multiple ? 'files' : 'a file'} here, or{' '}
          <button type="button" className="font-medium text-brand-600 underline decoration-brand-300 underline-offset-2 hover:text-brand-700" onClick={() => inputRef.current?.click()}>
            browse
          </button>
        </p>
        <p className="text-xs text-slate-400">
          {ACCEPTED_EXTENSIONS.join(', ')} · up to {MAX_UPLOAD_MB} MB
        </p>
        <input
          ref={inputRef}
          type="file"
          hidden
          multiple={multiple}
          accept={ACCEPTED_EXTENSIONS.join(',')}
          aria-label={`${title} file`}
          onChange={(e) => {
            void uploadFiles(Array.from(e.target.files ?? []))
            e.target.value = ''
          }}
        />
        {busy && <p className="text-xs text-brand-600">Uploading…</p>}
      </div>

      {allowPaste && (
        <div className="space-y-2">
          {!pasting ? (
            <Button variant="ghost" onClick={() => setPasting(true)}>
              …or paste text instead
            </Button>
          ) : (
            <>
              <Textarea
                rows={8}
                value={pasted}
                onChange={(e) => setPasted(e.target.value)}
                placeholder="Paste the job description here"
                aria-label="Pasted text"
              />
              <div className="flex gap-2">
                <Button onClick={submitPasted} disabled={busy || pasted.trim().length < 20}>
                  Use this text
                </Button>
                <Button variant="ghost" onClick={() => setPasting(false)}>
                  Cancel
                </Button>
              </div>
            </>
          )}
        </div>
      )}

      {error && (
        <p role="alert" className="whitespace-pre-line text-sm text-red-700">
          {error}
        </p>
      )}

      {documents.length > 0 && (
        <ul className="space-y-2">
          {documents.map((d) => (
            <DocumentRow key={d.id} doc={d} onDelete={remove} />
          ))}
        </ul>
      )}
    </Card>
  )
}
