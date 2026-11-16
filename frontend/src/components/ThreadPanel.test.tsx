import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import type { Thread } from '../api/types'
import { LinkScrollContext, createLinkScroll } from '../review/linkFocus'
import { ThreadPanel } from './ThreadPanel'

const outdated: Thread = {
  id: 't1',
  scope: 'unit',
  path: 'src/shop/cart.py',
  module: 'shop.cart',
  kind: 'function',
  qualified_name: 'total',
  side: 'head',
  status: 'open',
  resolvable: true,
  created_by: { id: 1, email: 'a@b.c', name: 'Alice', ai: false },
  created_at: '2026-10-28T10:00:00Z',
  line_text: 'return 0',
  line_count: 1,
  context_before: [],
  context_after: [],
  anchor: { revision_id: 1, line_offset: 1, outdated: true, unit_id: null, file_line: null, end_file_line: null },
  comments: [],
  can_delete: false,
}

const general: Thread = {
  ...outdated,
  id: 't2',
  scope: 'review',
  path: null,
  module: null,
  kind: null,
  qualified_name: null,
  side: null,
  resolvable: false,
  line_text: null,
  anchor: null,
}

const inline: Thread = {
  ...outdated,
  id: 't3',
  anchor: { revision_id: 1, line_offset: 1, outdated: false, unit_id: 7, file_line: 12, end_file_line: 12 },
  comments: [{ id: 'c1', thread_id: 't3', author: outdated.created_by, body: 'Why zero?\nMore text', created_at: '2026-10-28T10:00:00Z', edited_at: null, deleted: false, mine: false, remote_url: null }],
}

const resolved: Thread = { ...outdated, id: 't4', status: 'resolved', qualified_name: 'subtotal' }

function renderPanel(threads: Thread[]) {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <ThreadPanel reviewId={1} threads={threads} />
    </QueryClientProvider>,
  )
}

describe('ThreadPanel filters', () => {
  afterEach(() => {
    window.localStorage.clear()
  })

  it('shows general and code comments by default and filters each kind', () => {
    renderPanel([general, outdated, inline])

    expect(screen.getByRole('heading', { name: 'Review' })).toBeTruthy()
    expect(screen.getByRole('button', { name: 'total (src/shop/cart.py:12)' })).toBeTruthy()
    expect(screen.getByText('Alice: Why zero?')).toBeTruthy()

    fireEvent.click(screen.getByRole('tab', { name: 'General' }))
    expect(screen.queryByRole('heading', { name: 'In the code' })).toBeNull()
    expect(screen.queryByRole('heading', { name: 'Outdated or not shown' })).toBeNull()

    fireEvent.click(screen.getByRole('tab', { name: 'Code' }))
    expect(screen.queryByRole('heading', { name: 'Review' })).toBeNull()
    expect(screen.getByRole('heading', { name: 'In the code' })).toBeTruthy()
    expect(screen.getByRole('heading', { name: 'Outdated or not shown' })).toBeTruthy()
    expect(window.localStorage.getItem('bussola.conversationFilter')).toBe('code')
  })

  it('hides resolved threads until asked', () => {
    renderPanel([resolved])

    expect(screen.queryByText('subtotal')).toBeNull()

    fireEvent.click(screen.getByRole('checkbox', { name: 'Show resolved (1)' }))

    expect(screen.getByText('subtotal')).toBeTruthy()
  })

  it('shows a hidden thread that a link points at', () => {
    Element.prototype.scrollIntoView = () => undefined
    window.localStorage.setItem('bussola.conversationFilter', 'general')
    const link = createLinkScroll()
    render(
      <QueryClientProvider client={new QueryClient()}>
        <LinkScrollContext value={link}>
          <ThreadPanel reviewId={1} threads={[resolved]} />
        </LinkScrollContext>
      </QueryClientProvider>,
    )
    expect(screen.queryByText('subtotal')).toBeNull()

    act(() => { link.start({ unitId: null, elementId: 'thread-t4' }) })

    expect(screen.getByText('subtotal')).toBeTruthy()
    expect(screen.getByRole('checkbox', { name: 'Show resolved (1)' })).toBeChecked()
    expect(screen.getByRole('tab', { name: 'All' })).toHaveAttribute('aria-selected', 'true')
    Reflect.deleteProperty(Element.prototype, 'scrollIntoView')
  })
})

describe('ThreadPanel', () => {
  it('names the unit of a thread shown outside its card with its module', () => {
    const { container } = render(
      <QueryClientProvider client={new QueryClient()}>
        <ThreadPanel reviewId={1} threads={[outdated]} />
      </QueryClientProvider>,
    )

    const location = container.querySelector('.thread-location')
    expect(location?.querySelector('.qualified-name')).toHaveAttribute('title', 'shop.cart.total')
    expect(location?.querySelector('.unit-module')?.textContent).toContain('shop.cart.')
    expect(screen.getByText('total')).toHaveClass('unit-name')
    expect(location).toHaveTextContent('in src/shop/cart.py')
  })
})
