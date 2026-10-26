import { X } from 'lucide-react'
import { useState } from 'react'

interface Props {
  label: string
  items: string[]
  onChange: (items: string[]) => void
  tone?: 'brand' | 'slate'
}

/** Editable list of short strings: remove with the x button, add with Enter. */
export function ChipList({ label, items, onChange, tone = 'brand' }: Props) {
  const [draft, setDraft] = useState('')
  const chip = tone === 'brand' ? 'bg-brand-50 text-brand-700' : 'bg-slate-100 text-slate-700'

  function add() {
    const value = draft.trim()
    if (value && !items.some((i) => i.toLowerCase() === value.toLowerCase())) onChange([...items, value])
    setDraft('')
  }

  return (
    <div className="space-y-2">
      <p className="text-sm font-medium text-slate-700">{label}</p>
      <ul className="flex flex-wrap gap-1.5">
        {items.length === 0 && <li className="text-sm text-slate-400">None</li>}
        {items.map((item) => (
          <li key={item} className={`inline-flex items-center gap-1 rounded-full py-0.5 pl-2.5 pr-1 text-xs ${chip}`}>
            {item}
            <button
              type="button"
              className="rounded-full p-0.5 hover:bg-black/10"
              aria-label={`Remove ${item}`}
              onClick={() => onChange(items.filter((i) => i !== item))}
            >
              <X className="size-3" />
            </button>
          </li>
        ))}
      </ul>
      <input
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter') {
            e.preventDefault()
            add()
          }
        }}
        onBlur={add}
        placeholder="Add and press Enter"
        aria-label={`Add to ${label}`}
        className="w-48 rounded-md border border-slate-300 px-2 py-1 text-xs focus:border-brand-500 focus:outline-none"
      />
    </div>
  )
}
