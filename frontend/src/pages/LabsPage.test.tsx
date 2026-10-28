import { render, screen } from '@testing-library/react'
import { vi } from 'vitest'
import { LabsPage } from './LabsPage'

afterEach(() => vi.unstubAllGlobals())

it('shows all Phase 7 labs and fails closed when no runner is configured', async () => {
  vi.stubGlobal('fetch', vi.fn(async (url: string) => {
    if (url.endsWith('/labs/coding')) return new Response(JSON.stringify({ enabled: false, languages: ['python', 'javascript'], max_code_chars: 20000, timeout_seconds: 8 }))
    return new Response(JSON.stringify([]))
  }))
  render(<LabsPage />)
  expect(await screen.findByText('Runner disabled')).toBeInTheDocument()
  expect(screen.getByRole('heading', { name: 'Secure code workspace' })).toBeInTheDocument()
  expect(screen.getByRole('heading', { name: 'Practise for a specific company' })).toBeInTheDocument()
  expect(screen.getByRole('heading', { name: 'Architecture portfolio' })).toBeInTheDocument()
  expect(screen.getByRole('button', { name: /Run safely/ })).toBeDisabled()
})
