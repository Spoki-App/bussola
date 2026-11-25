import { act, fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import type { Thread } from '../api/types'
import { LinkScrollContext, createLinkScroll } from '../review/linkFocus'
import { ResolvedThreadsMarker } from './ResolvedThreadsMarker'

function resolved(id: string): Thread {
  return {
    id,
    scope: 'unit',
    path: 'app.py',
    module: null,
    kind: null,
    qualified_name: null,
    side: 'head',
    status: 'resolved',
    resolvable: true,
    created_by: { id: 1, email: 'a@b.c', name: 'Alice', ai: false },
    created_at: '2026-10-28T10:00:00Z',
    line_text: 'return 0',
    line_count: 1,
    context_before: [],
    context_after: [],
    anchor: { revision_id: 1, line_offset: 0, outdated: false, unit_id: 7, file_line: 12, end_file_line: 12 },
    comments: [],
    can_delete: false,
  }
}

describe('ResolvedThreadsMarker', () => {
  it('names one resolved thread and toggles it', () => {
    const onShow = vi.fn()
    const { rerender } = render(<ResolvedThreadsMarker threads={[resolved('t1')]} expanded={false} onShow={onShow} />)

    const marker = screen.getByRole('button', { name: '1 resolved thread' })
    expect(marker).toHaveAttribute('title', '1 resolved thread')
    expect(marker).toHaveAttribute('aria-expanded', 'false')
    expect(marker).toHaveTextContent('')
    fireEvent.click(marker)
    expect(onShow).toHaveBeenLastCalledWith(true)

    rerender(<ResolvedThreadsMarker threads={[resolved('t1')]} expanded onShow={onShow} />)
    fireEvent.click(marker)
    expect(onShow).toHaveBeenLastCalledWith(false)
  })

  it('lets a press on it reach the window, which ends following a link', () => {
    const onWindowMouseDown = vi.fn()
    window.addEventListener('mousedown', onWindowMouseDown)
    render(<ResolvedThreadsMarker threads={[resolved('t1')]} expanded={false} onShow={() => undefined} />)

    fireEvent.mouseDown(screen.getByRole('button', { name: '1 resolved thread' }))

    expect(onWindowMouseDown).toHaveBeenCalledOnce()
    window.removeEventListener('mousedown', onWindowMouseDown)
  })

  it('counts several resolved threads on the same line', () => {
    render(<ResolvedThreadsMarker threads={[resolved('t1'), resolved('t2')]} expanded={false} onShow={() => undefined} />)

    expect(screen.getByRole('button', { name: '2 resolved threads' })).toHaveTextContent('2')
  })

  it.each([
    ['the thread', { unitId: 7, elementId: 'thread-t2' }],
    ['its lines', { unitId: 7, elementId: 'unit-7', line: 12, lastLine: 12 }],
  ])('shows its threads when a link points at %s', (_, target) => {
    const link = createLinkScroll()
    const onShow = vi.fn()
    render(
      <LinkScrollContext value={link}>
        <ResolvedThreadsMarker threads={[resolved('t1'), resolved('t2')]} expanded={false} onShow={onShow} />
      </LinkScrollContext>,
    )

    act(() => { link.start({ unitId: 7, elementId: 'unit-7', line: 13 }) })
    expect(onShow).not.toHaveBeenCalled()

    act(() => { link.start(target) })
    expect(onShow).toHaveBeenCalledExactlyOnceWith(true)
  })
})
