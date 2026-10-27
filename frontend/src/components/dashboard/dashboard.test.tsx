import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import type { Dashboard } from '../../lib/api'
import { BadgesCard } from './BadgesCard'
import { NextActionCard } from './NextActionCard'
import { StatCard } from './StatCard'
import { TipCard } from './TipCard'
import { TrendChart } from './TrendChart'
import { TIPS, tipOfTheDay } from './tips'

const points = [
  { id: 'a', label: 'First try', date: '2026-10-20T10:00:00Z', score: 40 },
  { id: 'b', label: 'Second try', date: '2026-10-22T10:00:00Z', score: 62 },
  { id: 'c', label: 'Third try', date: '2026-10-25T10:00:00Z', score: 81 },
]

describe('TrendChart', () => {
  it('describes itself for screen readers and labels the latest value', () => {
    render(<TrendChart points={points} />)
    expect(screen.getByRole('img', { name: 'Score over time: 3 interviews, latest 81 out of 100' })).toBeInTheDocument()
    expect(screen.getByText('81')).toBeInTheDocument()
  })

  it('gives every point an accessible name and a keyboard tooltip', async () => {
    render(<TrendChart points={points} />)
    const point = screen.getByLabelText(/Second try, .*: 62 out of 100/)
    expect(point).toHaveAttribute('tabindex', '0')
    await userEvent.tab() // the 'Show table' button comes first
    await userEvent.tab() // then the first point
    await userEvent.tab() // then the second
    expect(screen.getByRole('tooltip')).toHaveTextContent('Second try')
    expect(screen.getByRole('tooltip')).toHaveTextContent('62')
  })

  it('draws a line only when there is more than one point and a single marker otherwise', () => {
    const { container, rerender } = render(<TrendChart points={points.slice(0, 1)} />)
    expect(container.querySelector('path')).toBeNull()
    expect(screen.getByLabelText(/First try/)).toBeInTheDocument()
    rerender(<TrendChart points={points} />)
    expect(container.querySelector('path')).not.toBeNull()
  })

  it('offers the same numbers as a table', async () => {
    render(<TrendChart points={points} />)
    await userEvent.click(screen.getByRole('button', { name: 'Show table' }))
    expect(screen.getByRole('cell', { name: 'Third try' })).toBeInTheDocument()
    expect(screen.getAllByRole('row')).toHaveLength(4)
    await userEvent.click(screen.getByRole('button', { name: 'Show chart' }))
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
  })

  it('keeps out-of-range scores on the chart', () => {
    const { container } = render(<TrendChart points={[{ ...points[0], score: 140 }, { ...points[1], score: -20 }]} />)
    const ys = [...container.querySelectorAll('circle[r="5"]')].map((c) => Number(c.getAttribute('cy')))
    expect(ys[0]).toBeLessThan(ys[1])
    expect(ys.every((y) => y >= 0 && y <= 300)).toBe(true)
  })
})

describe('StatCard', () => {
  it('shows an arrow and sign for change, so colour is never the only signal', () => {
    const { rerender } = render(<StatCard label="Latest score" value={72} change={12} icon={<span />} />)
    expect(screen.getByText('▲ +12')).toBeInTheDocument()
    rerender(<StatCard label="Latest score" value={60} change={-5} icon={<span />} />)
    expect(screen.getByText('▼ -5')).toBeInTheDocument()
    rerender(<StatCard label="Latest score" value={60} change={0} icon={<span />} />)
    expect(screen.getByText('no change')).toBeInTheDocument()
    rerender(<StatCard label="Latest score" value="—" change={null} hint="out of 100" icon={<span />} />)
    expect(screen.getByText('out of 100')).toBeInTheDocument()
  })
})

describe('NextActionCard', () => {
  const action = (kind: Dashboard['next_action']['kind'], href: string): Dashboard['next_action'] => ({ kind, title: 'T', label: `Label ${kind}`, description: `Why ${kind}`, session_id: 's1', href })

  it.each([['continue', '/sessions/s1/interview'], ['report', '/sessions/s1/report'], ['start', '/sessions/s1/plan'], ['plan', '/sessions/s1/analysis'], ['analyse', '/sessions/s1/upload'], ['upload', '/sessions/s1/upload']] as const)(
    'links the %s step to the right page',
    (kind, href) => {
      render(<MemoryRouter><NextActionCard action={action(kind, href)} /></MemoryRouter>)
      expect(screen.getByRole('heading', { name: `Label ${kind}` })).toBeInTheDocument()
      expect(screen.getByRole('link', { name: /Continue/ })).toHaveAttribute('href', href)
    },
  )

  it('invites a brand-new user to get started', () => {
    render(<MemoryRouter><NextActionCard action={{ ...action('new', '/new'), session_id: null, title: null }} /></MemoryRouter>)
    expect(screen.getByRole('link', { name: /Get started/ })).toHaveAttribute('href', '/new')
  })
})

describe('BadgesCard', () => {
  it('counts earned milestones and says what is needed for the rest', () => {
    render(<BadgesCard badges={[{ id: 'a', label: 'First interview', description: 'Finish your first mock interview', earned: true }, { id: 'b', label: 'Strong showing', description: 'Score 70 or more', earned: false }]} />)
    expect(screen.getByText('1 of 2')).toBeInTheDocument()
    expect(screen.getByText('Earned')).toBeInTheDocument()
    expect(screen.getByText('Score 70 or more')).toBeInTheDocument()
  })
})

describe('tips', () => {
  it('shows a tip, and the next button cycles through them', async () => {
    render(<TipCard />)
    const first = screen.getByRole('heading', { level: 3 }).textContent
    await userEvent.click(screen.getByRole('button', { name: 'Next tip' }))
    expect(screen.getByRole('heading', { level: 3 }).textContent).not.toBe(first)
  })

  it('picks the same tip all day and a different one tomorrow', () => {
    expect(tipOfTheDay(new Date(2026, 9, 27, 8))).toBe(tipOfTheDay(new Date(2026, 9, 27, 22)))
    expect(tipOfTheDay(new Date(2026, 9, 28))).toBe((tipOfTheDay(new Date(2026, 9, 27)) + 1) % TIPS.length)
  })

  it('every tip has a title and real advice', () => {
    expect(TIPS.length).toBeGreaterThanOrEqual(10)
    for (const t of TIPS) expect(t.title.length > 3 && t.text.length > 40).toBe(true)
  })
})
