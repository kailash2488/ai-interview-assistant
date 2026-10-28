import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ThemeToggle } from './ThemeToggle'
import { THEME_KEY } from '../lib/theme'

beforeEach(() => {
  localStorage.clear()
  document.documentElement.classList.remove('dark')
})

it('persists a selected dark theme', async () => {
  render(<ThemeToggle />)
  await userEvent.click(screen.getByRole('button', { name: 'Dark' }))
  expect(localStorage.getItem(THEME_KEY)).toBe('dark')
  expect(document.documentElement).toHaveClass('dark')
  expect(screen.getByRole('button', { name: 'Dark' })).toHaveAttribute('aria-pressed', 'true')
})

it('offers light, dark and system preferences', () => {
  render(<ThemeToggle />)
  expect(screen.getAllByRole('button').map((button) => button.textContent)).toEqual(['Light', 'Dark', 'System'])
})
