import type { DocumentStatus } from '../lib/api'
import { Badge, type Tone } from './ui/badge'

const MAP: Record<DocumentStatus, { label: string; tone: Tone }> = {
  uploaded: { label: 'Uploaded', tone: 'neutral' },
  parsing: { label: 'Parsing…', tone: 'info' },
  ready: { label: 'Ready', tone: 'success' },
  failed: { label: 'Failed', tone: 'danger' },
}

export function StatusBadge({ status }: { status: DocumentStatus }) {
  const { label, tone } = MAP[status]
  return <Badge tone={tone}>{label}</Badge>
}
