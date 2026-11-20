import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { CompareBar } from './CompareBar'

function stubClipboard(readText: () => Promise<string>) {
  Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { readText } })
}

function renderBar(props: Partial<Parameters<typeof CompareBar>[0]> = {}) {
  const handlers = { onCompareClipboard: vi.fn(), onCancel: vi.fn() }
  render(<CompareBar title="checkout.validate" lineCount={5} {...handlers} {...props} />)
  return handlers
}

describe('CompareBar', () => {
  afterEach(() => {
    Reflect.deleteProperty(navigator, 'clipboard')
  })

  it('shows the first range as a chip and asks for a second range', () => {
    renderBar()

    expect(screen.getByRole('status', { name: 'Compare ranges' })).toBeInTheDocument()
    expect(screen.getByText('checkout.validate')).toBeInTheDocument()
    expect(screen.getByText('5 lines')).toBeInTheDocument()
    expect(screen.getByText('Select a second range by its line numbers, or compare with the clipboard.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Compare with selection' })).toBeDisabled()
  })

  it('compares with the selected lines once a second range is selected', () => {
    const onCompareSelection = vi.fn()
    const handlers = { onCompareClipboard: vi.fn(), onCancel: vi.fn() }
    const { rerender } = render(<CompareBar title="checkout.validate" lineCount={5} {...handlers} />)
    expect(screen.getByRole('button', { name: 'Compare with selection' })).toBeDisabled()

    rerender(<CompareBar title="checkout.validate" lineCount={5} {...handlers} onCompareSelection={onCompareSelection} />)

    expect(screen.getByText('Compare it with the selected lines or the clipboard.')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Compare with selection' }))
    expect(onCompareSelection).toHaveBeenCalledOnce()
  })

  it('offers the clipboard as an icon button named in its tooltip', () => {
    renderBar()

    const button = screen.getByRole('button', { name: 'Compare with clipboard' })
    expect(button).toHaveClass('icon-button')
    expect(button).toHaveAttribute('title', 'Compare with clipboard')
    expect(button).toHaveTextContent('')
  })

  it('compares with the text in the clipboard', async () => {
    stubClipboard(() => Promise.resolve('return total\n'))
    const { onCompareClipboard } = renderBar()

    fireEvent.click(screen.getByRole('button', { name: 'Compare with clipboard' }))

    await vi.waitFor(() => { expect(onCompareClipboard).toHaveBeenCalledWith('return total\n') })
  })

  it('does not compare when the clipboard is read after the bar closed', async () => {
    let resolve: (text: string) => void = () => undefined
    const read = new Promise<string>((done) => { resolve = done })
    stubClipboard(() => read)
    const handlers = { onCompareClipboard: vi.fn(), onCancel: vi.fn() }
    const { unmount } = render(<CompareBar title="checkout.validate" lineCount={5} {...handlers} />)

    fireEvent.click(screen.getByRole('button', { name: 'Compare with clipboard' }))
    unmount()
    resolve('return total\n')
    await read

    expect(handlers.onCompareClipboard).not.toHaveBeenCalled()
  })

  it('says when the clipboard is empty', async () => {
    stubClipboard(() => Promise.resolve('  \n'))
    const { onCompareClipboard } = renderBar()

    fireEvent.click(screen.getByRole('button', { name: 'Compare with clipboard' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('The clipboard has no text to compare.')
    expect(onCompareClipboard).not.toHaveBeenCalled()
  })

  it('says when the clipboard cannot be read', async () => {
    stubClipboard(() => Promise.reject(new Error('denied')))
    renderBar()

    fireEvent.click(screen.getByRole('button', { name: 'Compare with clipboard' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('The clipboard could not be read.')
  })

  it('cancels the comparison', () => {
    const { onCancel } = renderBar()

    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))

    expect(onCancel).toHaveBeenCalledOnce()
  })
})
