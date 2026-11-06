import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { DiffRow, Unit, UnitDiff, UnitState } from '../api/types'
import { LinkScrollContext, createLinkScroll } from '../review/linkFocus'
import { ReviewLinkContext, reviewLinkMaker } from '../review/reviewLink'
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
        <UnitCard reviewId={1} repoId={1} unit={unit(state)} focused={false} onFocus={() => undefined} register={() => undefined} />
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
            <UnitCard reviewId={1} repoId={1} unit={unit('approved')} focused={false} onFocus={() => undefined} register={() => undefined} />
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
          <UnitCard reviewId={1} repoId={1} unit={unit('changed')} focused={false} onFocus={() => undefined} register={() => undefined} />
        </LinkScrollContext>
      </QueryClientProvider>,
    )

    act(() => { link.start({ unitId: 1, elementId: 'unit-1' }) })

    await waitFor(() => { expect(link.current()?.reached).toBe(true) })
    Reflect.deleteProperty(Element.prototype, 'scrollIntoView')
  })

  it('offers a link to its first line only in a pull request review', () => {
    vi.stubGlobal('fetch', vi.fn(() => new Promise(() => undefined)))
    const client = new QueryClient()
    const card = (makeLink: ReturnType<typeof reviewLinkMaker>, overrides: Partial<Unit>) => (
      <QueryClientProvider client={client}>
        <ReviewLinkContext value={makeLink}>
          <UnitCard reviewId={1} repoId={1} unit={unit('approved', overrides)} focused={false} onFocus={() => undefined} register={() => undefined} />
        </ReviewLinkContext>
      </QueryClientProvider>
    )
    const makeLink = reviewLinkMaker('https://github.com/acme/widgets/pull/3')
    const { rerender } = render(card(makeLink, { head_start: 12, head_end: 20 }))
    expect(screen.getByRole('button', { name: 'Copy link to this unit' })).toBeInTheDocument()

    rerender(card(makeLink, { head_start: null, head_end: null }))
    expect(screen.queryByRole('button', { name: 'Copy link to this unit' })).toBeNull()

    rerender(card(null, { head_start: 12, head_end: 20 }))
    expect(screen.queryByRole('button', { name: 'Copy link to this unit' })).toBeNull()
  })

  it('shows the module before the name of every unit, methods included', () => {
    vi.stubGlobal('fetch', vi.fn(() => new Promise(() => undefined)))
    const client = new QueryClient()
    const card = (overrides: Partial<Unit>) => (
      <QueryClientProvider client={client}>
        <UnitCard reviewId={1} repoId={1} unit={unit('approved', overrides)} focused={false} onFocus={() => undefined} register={() => undefined} />
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

  it('opens a jump target and shows the base diff when the target is on the base side', () => {
    const fetchMock = vi.fn<(url: string) => Promise<never>>(() => new Promise(() => undefined))
    vi.stubGlobal('fetch', fetchMock)
    Element.prototype.scrollIntoView = vi.fn()
    const client = new QueryClient()
    const card = (target?: { unitId: number; line: number; side: 'head' | 'base' }) => (
      <QueryClientProvider client={client}>
        <UnitCard reviewId={1} repoId={1} unit={unit('approved')} focused={false} onFocus={() => undefined} register={() => undefined} navigationTarget={target} />
      </QueryClientProvider>
    )
    const { rerender } = render(card())
    expect(disclosure()).toHaveAttribute('aria-expanded', 'false')

    rerender(card({ unitId: 1, line: 3, side: 'head' }))
    expect(disclosure()).toHaveAttribute('aria-expanded', 'true')
    expect(fetchMock.mock.calls.map(([url]) => url).filter((url) => url.includes('/diff'))).toEqual(['/api/reviews/1/units/1/diff'])

    rerender(card({ unitId: 1, line: 3, side: 'base' }))
    expect(fetchMock.mock.calls.map(([url]) => url).at(-1)).toBe('/api/reviews/1/units/1/diff?mode=base')
  })
  it('drops the line selection when the diff shows other rows', async () => {
    const line = (change: DiffRow['change'], oldIndex: number | null, newIndex: number | null, text: string): DiffRow => ({
      change,
      old_index: oldIndex,
      new_index: newIndex,
      old_line: oldIndex === null ? null : oldIndex + 1,
      new_line: newIndex === null ? null : newIndex + 1,
      text,
      row_hash: change === 'context' ? null : text,
      approved: false,
      selection_id: null,
      placeholder: false,
    })
    const diffOf = (mode: UnitDiff['mode'], text: string): UnitDiff => ({
      unit_id: 1,
      mode,
      available_modes: ['base', 'approved'],
      approved_text_unavailable: false,
      binary: false,
      unified: 'diff --git a/app.py b/app.py\n--- a/app.py\n+++ b/app.py\n',
      rows: [line('context', 0, 0, 'TOTAL = 0'), line('added', null, 1, text)],
    })
    vi.stubGlobal('fetch', vi.fn((url: string) => {
      if (!url.includes('/diff')) {
        return new Promise(() => undefined)
      }
      return Promise.resolve(Response.json(url.includes('mode=approved') ? diffOf('approved', 'LIMIT = 2') : diffOf('base', 'LIMIT = 1')))
    }))
    const { container } = render(
      <QueryClientProvider client={new QueryClient()}>
        <UnitCard reviewId={1} repoId={1} unit={unit('changed', { kind: 'module', qualified_name: '', row_approvable: true, rows_total: 1 })} focused={false} onFocus={() => undefined} register={() => undefined} />
      </QueryClientProvider>,
    )
    const codeCell = async (text: string) => {
      let cell: Element | undefined
      await waitFor(() => {
        cell = [...container.querySelectorAll('td.diff-code')].find((candidate) => candidate.textContent === text)
        expect(cell).toBeDefined()
      })
      return cell as Element
    }

    fireEvent.click(await codeCell('LIMIT = 1'))
    expect(screen.getByRole('button', { name: 'Approve selection (1)' })).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Approved → current' }))
    await codeCell('LIMIT = 2')

    expect(screen.queryByRole('button', { name: /Approve selection/ })).toBeNull()
  })
})
