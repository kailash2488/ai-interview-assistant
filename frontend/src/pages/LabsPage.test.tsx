import { render, screen } from '@testing-library/react'
import { vi } from 'vitest'
import { LabsPage } from './LabsPage'

afterEach(() => vi.unstubAllGlobals())

it('offers the browser sandbox while Python fails closed without a server runner', async () => {
  vi.stubGlobal('fetch', vi.fn(async (url: string) => {
    if (url.endsWith('/labs/coding'))
      return new Response(
        JSON.stringify({
          enabled: false,
          languages: ['python'],
          max_code_chars: 20000,
          timeout_seconds: 8,
          detail:
            'Python execution is disabled until an administrator configures the isolated runner.',
        }),
      )
    return new Response(JSON.stringify([]))
  }))
  render(<LabsPage />)
  expect(await screen.findByText('Python runner unavailable')).toBeInTheDocument()
  expect(screen.getByRole('heading', { name: 'JavaScript browser sandbox' })).toBeInTheDocument()
  expect(screen.getByRole('button', { name: /Run JavaScript/ })).toBeEnabled()
  expect(screen.getByRole('heading', { name: 'Optional server runner (Python)' })).toBeInTheDocument()
  expect(screen.getByRole('heading', { name: 'Practise for a specific company' })).toBeInTheDocument()
  expect(screen.getByRole('heading', { name: 'Architecture portfolio' })).toBeInTheDocument()
  expect(screen.getByRole('button', { name: /Run safely/ })).toBeDisabled()
})
