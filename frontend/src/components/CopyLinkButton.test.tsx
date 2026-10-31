import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { CopyLinkButton } from './CopyLinkButton'

function stubClipboard(writeText: (text: string) => Promise<void>) {
  Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText } })
}

describe('CopyLinkButton', () => {
  afterEach(() => {
    Reflect.deleteProperty(navigator, 'clipboard')
  })

  it('copies the link and says so', async () => {
    const writeText = vi.fn(() => Promise.resolve())
    stubClipboard(writeText)
    render(<CopyLinkButton link="bussola://review?repo=acme/widgets&pr=1" label="Copy link" text="Copy bussola link" />)

    fireEvent.click(screen.getByRole('button', { name: 'Copy link' }))

    expect(writeText).toHaveBeenCalledWith('bussola://review?repo=acme/widgets&pr=1')
    expect(await screen.findByText('Link copied')).toBeInTheDocument()
  })

  it('says when the clipboard refuses the link', async () => {
    stubClipboard(() => Promise.reject(new Error('denied')))
    render(<CopyLinkButton link="bussola://review?repo=acme/widgets&pr=1" label="Copy link" />)
    const button = screen.getByRole('button', { name: 'Copy link' })

    fireEvent.click(button)

    await waitFor(() => { expect(button).toHaveAttribute('title', 'Copy failed') })
    expect(button).toHaveClass('failed')
  })
})
