import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import type { Thread } from '../api/types'
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
  created_by: { id: 1, email: 'a@b.c', name: 'Alice' },
  created_at: '2026-10-28T10:00:00Z',
  line_text: 'return 0',
  line_count: 1,
  context_before: [],
  context_after: [],
  anchor: { revision_id: 1, line_offset: 1, outdated: true, unit_id: null, file_line: null, end_file_line: null },
  comments: [],
  can_delete: false,
}

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
