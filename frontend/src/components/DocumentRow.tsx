import { ChevronDown, ChevronRight, FileText, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { api, type DocumentDetail, type DocumentItem } from '../lib/api'
import { StatusBadge } from './StatusBadge'
import { Button } from './ui/button'

export function DocumentRow({ doc, onDelete }: { doc: DocumentItem; onDelete: (doc: DocumentItem) => void }) {
  const [open, setOpen] = useState(false)
  const [detail, setDetail] = useState<DocumentDetail | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)

  async function toggle() {
    const next = !open
    setOpen(next)
    if (next && !detail) {
      try {
        setDetail(await api.getDocument(doc.session_id, doc.id))
      } catch (e) {
        setLoadError(e instanceof Error ? e.message : 'Could not load text')
      }
    }
  }

  return (
    <li className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
      <div className="flex items-center gap-3">
        <FileText className="size-4 shrink-0 text-slate-500" aria-hidden />
        <span className="min-w-0 flex-1 truncate text-sm" title={doc.filename}>
          {doc.filename}
        </span>
        <StatusBadge status={doc.status} />
        {doc.status === 'ready' && (
          <Button variant="ghost" className="px-2 py-1" onClick={toggle} aria-expanded={open}>
            {open ? <ChevronDown className="size-4" /> : <ChevronRight className="size-4" />}
            Text
          </Button>
        )}
        <Button variant="danger" className="px-2 py-1" onClick={() => onDelete(doc)} aria-label={`Remove ${doc.filename}`}>
          <Trash2 className="size-4" />
        </Button>
      </div>
      {doc.status === 'failed' && doc.error && <p className="mt-2 text-sm text-red-700">{doc.error}</p>}
      {open && (
        <div className="mt-3 space-y-3">
          {loadError && <p className="text-sm text-red-700">{loadError}</p>}
          {!detail && !loadError && <p className="text-sm text-slate-500">Loading…</p>}
          {detail?.sections_json && (
            <div className="flex flex-wrap gap-1.5">
              {detail.sections_json.map((s, i) => (
                <span key={`${s.name}-${i}`} className="rounded bg-brand-50 px-2 py-0.5 text-xs text-brand-700">
                  {s.name}
                </span>
              ))}
            </div>
          )}
          {detail && (
            <pre className="max-h-72 overflow-auto whitespace-pre-wrap rounded-md bg-white p-3 text-xs leading-relaxed text-slate-800 ring-1 ring-slate-200">
              {detail.raw_text}
            </pre>
          )}
        </div>
      )}
    </li>
  )
}
