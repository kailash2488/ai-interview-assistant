import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ScoreBars } from './ScoreBars'

const bars = [
  { label: 'Python', value: 80, detail: '2 answers' },
  { label: 'Docker', value: 20, detail: '1 answer' },
]

describe('ScoreBars', () => {
  it('shows each category with its value and an accessible name', () => {
    render(<ScoreBars title="Skill areas" bars={bars} />)
    expect(screen.getByLabelText('Python: 80 out of 100, 2 answers')).toBeInTheDocument()
    expect(screen.getByLabelText('Docker: 20 out of 100, 1 answer')).toBeInTheDocument()
    expect(screen.getAllByText('80').length).toBeGreaterThan(0)
  })

  it('shows a tooltip on hover and on keyboard focus, and hides it afterwards', async () => {
    render(<ScoreBars title="Skill areas" bars={bars} />)
    await userEvent.hover(screen.getByLabelText(/^Python/))
    expect(screen.getByRole('tooltip')).toHaveTextContent('80')
    await userEvent.unhover(screen.getByLabelText(/^Python/))
    expect(screen.queryByRole('tooltip')).not.toBeInTheDocument()
    await userEvent.tab()
    await userEvent.tab()
    expect(screen.getByRole('tooltip')).toBeInTheDocument()
  })

  it('offers the same data as a table', async () => {
    render(<ScoreBars title="Skill areas" bars={bars} valueLabel="Score" />)
    await userEvent.click(screen.getByRole('button', { name: 'Show table' }))
    expect(screen.getByRole('table')).toBeInTheDocument()
    expect(screen.getByRole('cell', { name: 'Docker' })).toBeInTheDocument()
    expect(screen.getByRole('cell', { name: '2 answers' })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Show chart' }))
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
  })

  it('clamps out-of-range values so a bar never overflows', () => {
    render(<ScoreBars title="t" bars={[{ label: 'X', value: 140 }, { label: 'Y', value: -5 }]} />)
    const fills = document.querySelectorAll<HTMLElement>('span[style*="background"]')
    expect([...fills].map((f) => f.style.width)).toEqual(['100%', '0%'])
  })
})
