import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest'

import type { CodeRange, Comparison, DiffRow } from '../api/types'
import { CompareDialog } from './CompareDialog'

function code(name: string, side: CodeRange['side'], first: number): CodeRange {
  return { unit_id: 1, side, line_offset: 0, line_count: 2, path: 'shop.py', qualified_name: name, kind: 'function', first_line: first, last_line: first + 1 }
}

function row(change: DiffRow['change'], oldLine: number | null, newLine: number | null, text: string): DiffRow {
  return { change, old_index: oldLine, new_index: newLine, old_line: oldLine, new_line: newLine, text, row_hash: null, approved: false, selection_id: null, placeholder: false }
}

const COMPARISON: Comparison = {
  left: code('checkout', 'base', 4),
  right: code('validate', 'head', 9),
  identical: false,
  unified: 'diff --git a/shop.py b/shop.py\n--- a/shop.py\n+++ b/shop.py\n@@ -1,2 +1,2 @@\n for item in items:\n-    check(item, 1)\n+    check(item, 2)\n',
  rows: [row('context', 0, 0, 'for item in items:'), row('removed', 1, null, '    check(item, 1)'), row('added', null, 1, '    check(item, 2)')],
}

const REQUEST = { left: { unit_id: 1, side: 'base' as const, line_offset: 3, line_count: 2 }, right: { unit_id: 2, side: 'head' as const, line_offset: 8, line_count: 2 } }

describe('CompareDialog', () => {
  beforeAll(() => {
    HTMLDialogElement.prototype.showModal = function showModal(this: HTMLDialogElement) {
      this.open = true
    }
    HTMLDialogElement.prototype.close = function close(this: HTMLDialogElement) {
      this.open = false
      this.dispatchEvent(new Event('close'))
    }
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('asks for the two ranges and shows them side by side', async () => {
    const fetchMock = vi.fn<(url: string, init?: RequestInit) => Promise<Response>>(() => Promise.resolve(Response.json(COMPARISON)))
    vi.stubGlobal('fetch', fetchMock)
    const onClose = vi.fn()
    render(
      <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <CompareDialog reviewId={5} request={REQUEST} onClose={onClose} />
      </QueryClientProvider>,
    )

    const dialog = await screen.findByRole('dialog', { name: 'Compare' })
    expect(await within(dialog).findByText('changed')).toBeInTheDocument()
    expect(within(dialog).getByText('shop.py lines 4-5 (base)')).toBeInTheDocument()
    expect(within(dialog).getByText('shop.py lines 9-10')).toBeInTheDocument()
    expect(dialog.querySelector('.diff-split')).not.toBeNull()
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('/api/reviews/5/compare')
    expect(JSON.parse(typeof init?.body === 'string' ? init.body : '{}')).toEqual(REQUEST)

    fireEvent.click(within(dialog).getByRole('button', { name: 'Close' }))
    expect(onClose).toHaveBeenCalled()
  })

  it('names the clipboard as the left side of a comparison with pasted code', async () => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve(Response.json({ ...COMPARISON, left: null, identical: true }))))
    render(
      <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <CompareDialog reviewId={5} request={{ pasted: 'check(item, 1)', right: REQUEST.right }} onClose={vi.fn()} />
      </QueryClientProvider>,
    )

    const dialog = await screen.findByRole('dialog', { name: 'Compare' })
    expect(await within(dialog).findByText('identical')).toBeInTheDocument()
    expect(within(dialog).getByText('Clipboard')).toBeInTheDocument()
    expect(within(dialog).getByText('shop.py lines 9-10')).toBeInTheDocument()
  })
})
