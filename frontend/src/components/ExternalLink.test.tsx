import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { ExternalLink } from './ExternalLink'

describe('ExternalLink', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it('asks the rtool server to open GitHub links in the default browser', async () => {
    const fetchMock = vi.fn(() => Promise.resolve(Response.json({ opened: true })))
    vi.stubGlobal('fetch', fetchMock)
    const openSpy = vi.spyOn(window, 'open').mockReturnValue(null)
    render(<ExternalLink href="https://github.com/acme/widgets/pull/7">PR</ExternalLink>)

    fireEvent.click(screen.getByText('PR'))

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith('/api/open-url', expect.objectContaining({ method: 'POST', body: JSON.stringify({ url: 'https://github.com/acme/widgets/pull/7' }) }))
    })
    expect(openSpy).not.toHaveBeenCalled()
  })

  it('falls back to a new browser tab when the server cannot open the link', async () => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve(new Response(null, { status: 400 }))))
    const openSpy = vi.spyOn(window, 'open').mockReturnValue(null)
    render(<ExternalLink href="https://github.com/acme/widgets">repo</ExternalLink>)

    fireEvent.click(screen.getByText('repo'))

    await waitFor(() => {
      expect(openSpy).toHaveBeenCalledWith('https://github.com/acme/widgets', '_blank', 'noopener,noreferrer')
    })
  })

  it('leaves modified clicks to the browser', () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    render(<ExternalLink href="https://github.com/acme/widgets">repo</ExternalLink>)

    fireEvent.click(screen.getByText('repo'), { metaKey: true })

    expect(fetchMock).not.toHaveBeenCalled()
  })
})
