import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { useKeyboardShortcuts } from '../hooks/useKeyboardShortcuts'
import { Composer } from './Composer'
import { Markdown } from './Markdown'

function renderComposer(initial = '') {
  const onSubmit = vi.fn()
  render(<Composer submitLabel="Send" initial={initial} onSubmit={onSubmit} />)
  return { textbox: screen.getByRole<HTMLTextAreaElement>('textbox'), onSubmit }
}

describe('Composer preview', () => {
  it('renders the draft like a posted comment and keeps it when going back to write', () => {
    const text = '**bold** <script>alert(1)</script> | a |\n|---|\n| b |'
    const { textbox } = renderComposer(text)

    fireEvent.click(screen.getByRole('tab', { name: 'Preview' }))

    const preview = screen.getByRole('tabpanel')
    const posted = render(<Markdown text={text} />).container
    expect(preview.innerHTML).toBe(posted.innerHTML)
    expect(preview.querySelector('script')).toBeNull()
    expect(screen.queryByRole('toolbar')).toBeNull()

    fireEvent.click(screen.getByRole('tab', { name: 'Write' }))

    expect(textbox).toHaveValue(text)
    expect(textbox).toHaveFocus()
  })

  it('says there is nothing to preview for an empty comment', () => {
    renderComposer('  ')

    fireEvent.click(screen.getByRole('tab', { name: 'Preview' }))

    expect(screen.getByRole('tabpanel')).toHaveTextContent('Nothing to preview')
  })

  it('toggles the preview with Ctrl/Cmd + Shift + P', () => {
    const { textbox } = renderComposer('_hi_')

    fireEvent.keyDown(textbox, { key: 'P', metaKey: true, shiftKey: true })
    expect(screen.getByRole('tabpanel').querySelector('em')).toHaveTextContent('hi')

    fireEvent.keyDown(screen.getByRole('tabpanel'), { key: 'p', ctrlKey: true, shiftKey: true })
    expect(screen.queryByRole('tabpanel')).toBeNull()
    expect(textbox).toHaveFocus()
  })
})

describe('Composer formatting', () => {
  it('wraps the selection from the toolbar and keeps it selected', () => {
    const { textbox } = renderComposer('fix this')
    textbox.setSelectionRange(4, 8)

    fireEvent.click(screen.getByRole('button', { name: 'Bold' }))

    expect(textbox).toHaveValue('fix **this**')
    expect([textbox.selectionStart, textbox.selectionEnd]).toEqual([6, 10])

    fireEvent.click(screen.getByRole('button', { name: 'Bold' }))
    expect(textbox).toHaveValue('fix this')
  })

  it.each([
    ['b', 'Bold', '**bold text**'],
    ['i', 'Italic', '_italic text_'],
    ['e', 'Inline code', '`code`'],
    ['k', 'Link', '[text](url)'],
  ])('Ctrl/Cmd + %s applies %s at the cursor', (key, _label, expected) => {
    const { textbox } = renderComposer()
    const event = { key, ctrlKey: true }

    expect(fireEvent.keyDown(textbox, event)).toBe(false)

    expect(textbox).toHaveValue(expected)
  })

  it('does not trigger the review shortcuts', () => {
    const review = vi.fn()
    function Page() {
      useKeyboardShortcuts({ k: review, c: review })
      return <Composer submitLabel="Send" onSubmit={vi.fn()} />
    }
    render(<Page />)
    const textbox = screen.getByRole('textbox')

    fireEvent.keyDown(textbox, { key: 'k', metaKey: true })
    fireEvent.keyDown(textbox, { key: 'c' })

    expect(review).not.toHaveBeenCalled()
    expect(textbox).toHaveValue('[text](url)')
  })

  it('sends with Ctrl/Cmd + Enter', () => {
    const { textbox, onSubmit } = renderComposer('done')

    fireEvent.keyDown(textbox, { key: 'Enter', ctrlKey: true })

    expect(onSubmit).toHaveBeenCalledWith('done', expect.any(Function))
  })
})
