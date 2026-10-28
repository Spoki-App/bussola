import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { Unit, UnitState } from '../api/types'
import { UnitCard } from './UnitCard'

function unit(state: UnitState): Unit {
  return {
    id: 1,
    revision_id: 1,
    path: 'app.py',
    old_path: null,
    kind: 'function',
    qualified_name: 'total',
    state,
    change_type: 'modified',
    base_changed: false,
    approval_id: state === 'approved' ? 'a1' : null,
    row_approvable: false,
    rows_total: 0,
    rows_approved: 0,
    binary: false,
    image: false,
    open_threads: 0,
  }
}

function disclosure() {
  return screen.getByRole('button', { name: /Collapse unit|Expand unit/ })
}

describe('UnitCard', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('closes when approved and opens again when it needs review', () => {
    vi.stubGlobal('fetch', vi.fn(() => new Promise(() => undefined)))
    const client = new QueryClient()
    const card = (state: UnitState) => (
      <QueryClientProvider client={client}>
        <UnitCard reviewId={1} unit={unit(state)} focused={false} onFocus={() => undefined} register={() => undefined} />
      </QueryClientProvider>
    )
    const { rerender } = render(card('changed'))
    expect(disclosure()).toHaveAttribute('aria-expanded', 'true')

    rerender(card('approved'))
    expect(disclosure()).toHaveAttribute('aria-expanded', 'false')

    rerender(card('changed'))
    expect(disclosure()).toHaveAttribute('aria-expanded', 'true')
  })
})
