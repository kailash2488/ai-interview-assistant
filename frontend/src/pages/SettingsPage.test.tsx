import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { vi } from 'vitest'
import type { LLMSettings } from '../lib/api'
import { SettingsPage } from './SettingsPage'

const base: LLMSettings = {
  provider: 'ollama', gemini_model: 'gemini-3.8-flash',
  gemini_models: [
    { id: 'gemini-3.8-flash', label: 'Gemini 3.8 Flash', note: 'Newest', tier: 'free' },
    { id: 'gemini-3.1-pro-preview', label: 'Gemini 3.1 Pro (preview)', note: 'Strongest', tier: 'paid' },
  ],
  gemini_key_set: false, gemini_key_hint: null, gemini_key_source: 'none', ollama_model: 'mistral:7b',
}

function stub(handler: (url: string, init?: RequestInit) => [number, unknown]) {
  const fn = vi.fn(async (url: string, init?: RequestInit) => {
    const [status, body] = handler(url, init)
    return new Response(JSON.stringify(body), { status })
  })
  vi.stubGlobal('fetch', fn)
  return fn
}

const renderPage = () => render(<MemoryRouter><SettingsPage /></MemoryRouter>)
afterEach(() => vi.unstubAllGlobals())

describe('Settings page', () => {
  it('defaults to the free local model and hides key fields', async () => {
    stub(() => [200, base])
    renderPage()
    expect(await screen.findByLabelText(/Local model/)).toBeChecked()
    expect(screen.queryByLabelText('Gemini API key')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Save' })).toBeDisabled()
  })

  it('asks for a key when Gemini is chosen and will not save without one', async () => {
    stub(() => [200, base])
    renderPage()
    await userEvent.click(await screen.findByLabelText(/Google Gemini/))
    expect(screen.getByLabelText('Gemini API key')).toHaveAttribute('type', 'password')
    expect(screen.getByRole('button', { name: 'Save' })).toBeDisabled()
    expect(screen.getByText('Paste a key to use Gemini.')).toBeInTheDocument()
  })

  it('saves provider, model and key, then clears the key field and shows only a hint', async () => {
    const after: LLMSettings = { ...base, provider: 'gemini', gemini_key_set: true, gemini_key_hint: '…cdef', gemini_key_source: 'settings' }
    const fetchFn = stub((_u, init) => (init?.method === 'PUT' ? [200, after] : [200, base]))
    renderPage()
    await userEvent.click(await screen.findByLabelText(/Google Gemini/))
    await userEvent.type(screen.getByLabelText('Gemini API key'), 'AIzaSyKEY-abcdef')
    await userEvent.click(screen.getByRole('button', { name: 'Save' }))

    expect(await screen.findByRole('status')).toHaveTextContent('Saved')
    const put = fetchFn.mock.calls.find(([, i]) => i?.method === 'PUT')!
    expect(JSON.parse(put[1]!.body as string)).toEqual({ provider: 'gemini', gemini_model: 'gemini-3.8-flash', gemini_api_key: 'AIzaSyKEY-abcdef' })
    expect(screen.getByLabelText('Gemini API key')).toHaveValue('')
    expect(screen.getByText(/ending …cdef is saved/)).toBeInTheDocument()
    expect(screen.queryByText(/AIzaSyKEY/)).not.toBeInTheDocument()
  })

  it('does not resend a saved key when only the model changes', async () => {
    const saved: LLMSettings = { ...base, provider: 'gemini', gemini_key_set: true, gemini_key_hint: '…cdef', gemini_key_source: 'settings' }
    const fetchFn = stub((_u, init) => (init?.method === 'PUT' ? [200, { ...saved, gemini_model: 'gemini-3.1-pro-preview' }] : [200, saved]))
    renderPage()
    await userEvent.selectOptions(await screen.findByLabelText('Model'), 'gemini-3.1-pro-preview')
    await userEvent.click(screen.getByRole('button', { name: 'Save' }))
    await waitFor(() => expect(fetchFn.mock.calls.some(([, i]) => i?.method === 'PUT')).toBe(true))
    const put = fetchFn.mock.calls.find(([, i]) => i?.method === 'PUT')!
    expect(JSON.parse(put[1]!.body as string)).toEqual({ provider: 'gemini', gemini_model: 'gemini-3.1-pro-preview' })
  })

  it('shows the result of a connection test, including failures', async () => {
    stub((url) =>
      url.endsWith('/test')
        ? [200, { ok: false, provider: 'gemini', model: null, seconds: null, message: 'Gemini rejected the API key. Check it on the Settings page.' }]
        : [200, { ...base, provider: 'gemini', gemini_key_set: true, gemini_key_hint: '…cdef', gemini_key_source: 'settings' }],
    )
    renderPage()
    await userEvent.click(await screen.findByRole('button', { name: 'Test connection' }))
    expect(await screen.findByRole('status')).toHaveTextContent('rejected the API key')
  })

  it('removes a saved key after confirmation', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    const fetchFn = stub((_u, init) =>
      init?.method === 'DELETE' ? [200, base] : [200, { ...base, provider: 'gemini', gemini_key_set: true, gemini_key_hint: '…cdef', gemini_key_source: 'settings' }],
    )
    renderPage()
    await userEvent.click(await screen.findByRole('button', { name: 'Remove saved key' }))
    expect(await screen.findByLabelText(/Local model/)).toBeChecked()
    expect(fetchFn.mock.calls.some(([u, i]) => String(u).endsWith('/settings/llm/key') && i?.method === 'DELETE')).toBe(true)
  })

  it('shows a load error', async () => {
    stub(() => [500, { detail: 'boom' }])
    renderPage()
    expect(await screen.findByRole('alert')).toHaveTextContent('boom')
  })
})

describe('Settings page models', () => {
  it('lists the current models with their tier and warns when a paid one is chosen', async () => {
    stub(() => [200, { ...base, provider: 'gemini', gemini_key_set: true, gemini_key_hint: '…cdef', gemini_key_source: 'settings' }])
    renderPage()
    const select = await screen.findByLabelText('Model')
    expect(screen.getAllByRole('option').map((o) => o.textContent)).toEqual([
      'Gemini 3.8 Flash (free tier)',
      'Gemini 3.1 Pro (preview) (paid)',
    ])
    expect(screen.getByText(/Has a free tier/)).toBeInTheDocument()
    await userEvent.selectOptions(select, 'gemini-3.1-pro-preview')
    expect(screen.getByText(/needs a key from a project with billing/)).toBeInTheDocument()
  })
})
