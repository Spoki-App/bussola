import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { Unit, UnitState } from '../api/types'
import { LinkScrollContext, createLinkScroll } from '../review/linkFocus'
import { UnitCard } from './UnitCard'

function unit(state: UnitState, overrides: Partial<Unit> = {}): Unit {
  return {
    id: 1,
    revision_id: 1,
    path: 'app.py',
    old_path: null,
    module: null,
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
    todo: !state.startsWith('approved'),
    action: state.startsWith('approved') ? 'revoke' : 'approve',
    open_threads: 0,
    head_start: null,
    head_end: null,
    ...overrides,
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

  it('opens itself when a link points at it or at one of its threads', () => {
    vi.stubGlobal('fetch', vi.fn(() => new Promise(() => undefined)))
    Element.prototype.scrollIntoView = () => undefined
    for (const elementId of ['unit-1', 'thread-t']) {
      const link = createLinkScroll()
      const view = render(
        <QueryClientProvider client={new QueryClient()}>
          <LinkScrollContext value={link}>
            <UnitCard reviewId={1} unit={unit('approved')} focused={false} onFocus={() => undefined} register={() => undefined} />
          </LinkScrollContext>
        </QueryClientProvider>,
      )
      expect(disclosure()).toHaveAttribute('aria-expanded', 'false')

      act(() => { link.start({ unitId: 1, elementId }) })

      expect(disclosure()).toHaveAttribute('aria-expanded', 'true')
      view.unmount()
    }
    Reflect.deleteProperty(Element.prototype, 'scrollIntoView')
  })

  it('ends a link to the unit even when its diff cannot be loaded', async () => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve(Response.json({ detail: 'boom' }, { status: 500 }))))
    Element.prototype.scrollIntoView = () => undefined
    const link = createLinkScroll()
    render(
      <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <LinkScrollContext value={link}>
          <UnitCard reviewId={1} unit={unit('changed')} focused={false} onFocus={() => undefined} register={() => undefined} />
        </LinkScrollContext>
      </QueryClientProvider>,
    )

    act(() => { link.start({ unitId: 1, elementId: 'unit-1' }) })

    await waitFor(() => { expect(link.current()?.reached).toBe(true) })
    Reflect.deleteProperty(Element.prototype, 'scrollIntoView')
  })

  it('shows the module before the name of every unit, methods included', () => {
    vi.stubGlobal('fetch', vi.fn(() => new Promise(() => undefined)))
    const client = new QueryClient()
    const card = (overrides: Partial<Unit>) => (
      <QueryClientProvider client={client}>
        <UnitCard reviewId={1} unit={unit('approved', overrides)} focused={false} onFocus={() => undefined} register={() => undefined} />
      </QueryClientProvider>
    )
    const { container, rerender } = render(card({ kind: 'method', module: 'shop.billing.invoices', qualified_name: 'InvoiceService.create' }))
    expect(container.querySelector('.unit-header .qualified-name')).toHaveAttribute('title', 'shop.billing.invoices.InvoiceService.create')
    expect(container.querySelector('.unit-header .qualified-name')?.textContent).toBe('shop.billing.invoices.InvoiceService.create')
    expect(screen.getByText('create')).toHaveClass('unit-name')

    rerender(card({ module: 'shop.app', kind: 'module', qualified_name: '' }))
    expect(container.querySelector('.unit-module')).toBeNull()
    expect(screen.getByText('Module code')).toBeInTheDocument()
  })
})
