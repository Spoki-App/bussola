import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, fireEvent, render, renderHook, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'

import { UNSETTLED_ANSWER_MS, type Documentation, type NavigationResult, type NavigationTarget, type SourceFile } from '../api/navigation'
import { clearCaret, placeCaret } from '../test/caret'
import { useCodeNavigation } from './useCodeNavigation'

type NavigationReply = (params: URLSearchParams) => NavigationResult

const LIB = 'def price(item):\n    return item.cost\n\n\ndef discount(item):\n    return 0\n'
const CART = 'from lib import price\n\n\ndef total(items):\n    return price(items)\n'
const GITHUB = 'https://github.com/acme/widgets/blob/abc123'
const SHORTCUTS = '/work/.venv/lib/python3.12/site-packages/django/shortcuts.py'
const SHORTCUTS_SOURCE = 'def render(request, template_name):\n    pass\n'
const RENDER: Documentation = { qualified_name: 'django.shortcuts.render', package: 'Django', version: '5.1', url: 'https://docs.djangoproject.com/', text: null, source: null }

function target(path: string, line: number, unitId: number | null, role: NavigationTarget['role'] = 'definition'): NavigationTarget {
  return { role, path, line, column: 4, preview: `preview of ${path}:${String(line)}`, side: 'head', unit_id: unitId }
}

function found(targets: NavigationTarget[], overrides: Partial<NavigationResult> = {}): NavigationResult {
  return { ready: true, symbol: 'price', origin: 'reference', resolver: 'tree-sitter', targets, server_hint: null, documentation: null, ...overrides }
}

function json(body: unknown): Promise<Response> {
  return Promise.resolve(new Response(JSON.stringify(body), { status: 200, headers: { 'Content-Type': 'application/json' } }))
}

function serve(reply: NavigationReply, prepared: () => boolean = () => true) {
  const requests: URLSearchParams[] = []
  vi.stubGlobal(
    'fetch',
    vi.fn((input: string) => {
      const url = new URL(input, 'http://localhost')
      if (url.pathname.endsWith('/navigation/index')) {
        return json({ ready: prepared() })
      }
      if (url.pathname.endsWith('/navigation')) {
        requests.push(url.searchParams)
        return json(reply(url.searchParams))
      }
      if (url.pathname.endsWith('/library-source')) {
        return json({ path: url.searchParams.get('path'), text: SHORTCUTS_SOURCE, url: null })
      }
      const path = url.searchParams.get('path') ?? ''
      const source: SourceFile = { path, side: 'head', commit: 'abc123', text: path === 'lib.py' ? LIB : CART, url: `${GITHUB}/${path}` }
      return json(source)
    }),
  )
  return requests
}

function Harness() {
  const navigation = useCodeNavigation(1, 9, (unitId) => unitId === 4)
  return (
    <>
      <button type="button" onClick={() => { navigation.navigate({ path: 'cart.py', side: 'head', line: 5, column: 12, point: { x: 40, y: 60 } }) }}>
        Cmd+click price
      </button>
      <output aria-label="target">{navigation.target ? `${String(navigation.target.unitId)}:${String(navigation.target.line)}` : 'none'}</output>
      {navigation.element}
    </>
  )
}

function renderHarness() {
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <Harness />
    </QueryClientProvider>,
  )
  fireEvent.click(screen.getByRole('button', { name: 'Cmd+click price' }))
}

function cmdClickInModal(lineText: string, word: string) {
  const code = screen.getAllByText((_, element) => element?.tagName === 'CODE' && element.textContent === lineText)[0]
  const walker = document.createTreeWalker(code, NodeFilter.SHOW_TEXT)
  let node = walker.nextNode()
  while (node && !(node.textContent ?? '').includes(word)) {
    node = walker.nextNode()
  }
  const caret = node as Text
  placeCaret(caret, caret.data.indexOf(word) + 1)
  fireEvent.click(code, { metaKey: true, button: 0, clientX: 5, clientY: 5 })
}

describe('useCodeNavigation', () => {
  beforeAll(() => {
    HTMLDialogElement.prototype.showModal = function showModal(this: HTMLDialogElement) {
      this.open = true
    }
    HTMLDialogElement.prototype.close = function close(this: HTMLDialogElement) {
      if (this.open) {
        this.open = false
        this.dispatchEvent(new Event('close'))
      }
    }
    Element.prototype.scrollIntoView = vi.fn()
  })

  beforeEach(() => {
    window.localStorage.clear()
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
    clearCaret()
  })

  it('jumps straight to a single definition that is part of the review', async () => {
    const requests = serve(() => found([target('lib.py', 1, 4)]))
    renderHarness()

    expect(await screen.findByLabelText('target')).toHaveTextContent('4:1')
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(Object.fromEntries(requests[0])).toEqual({ side: 'head', revision_id: '9', path: 'cart.py', line: '5', column: '12' })
  })

  it('lists definitions first and usages by file, marks what is in the review and works with the keyboard', async () => {
    serve(() =>
      found([target('lib.py', 1, 4), target('other/lib.py', 3, null), target('cart.py', 5, 7, 'usage'), target('cart.py', 9, null, 'usage'), target('shop.py', 2, null, 'usage')]),
    )
    renderHarness()

    const popup = await screen.findByRole('dialog', { name: 'Definitions of price' })
    expect(within(popup).getByRole('region', { name: 'Definitions' })).toHaveTextContent('lib.py:1in reviewpreview of lib.py:1')
    expect(within(popup).getByRole('region', { name: 'Usages in cart.py' })).toHaveTextContent('2 usages')
    const entries = within(popup).getAllByRole('button')
    expect(entries.map((entry) => entry.querySelector('.navigation-location span')?.textContent)).toEqual(['lib.py:1', 'other/lib.py:3', 'cart.py:5', 'cart.py:9', 'shop.py:2'])
    expect(entries.map((entry) => within(entry).queryByText('in review') !== null)).toEqual([true, false, true, false, false])
    expect(entries[0]).toHaveFocus()

    fireEvent.keyDown(popup, { key: 'ArrowDown' })
    fireEvent.keyDown(popup, { key: 'ArrowDown' })
    expect(entries[2]).toHaveFocus()
    fireEvent.keyDown(popup, { key: 'ArrowUp' })
    fireEvent.keyDown(popup, { key: 'ArrowUp' })
    fireEvent.keyDown(popup, { key: 'ArrowUp' })
    expect(entries[4]).toHaveFocus()

    fireEvent.keyDown(popup, { key: 'ArrowDown' })
    expect(entries[0]).toHaveFocus()
    fireEvent.click(entries[0])
    expect(screen.getByLabelText('target')).toHaveTextContent('4:1')
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('opens targets outside the review in a modal with nested navigation, a back control and a GitHub link', async () => {
    serve((params) => (params.get('path') === 'lib.py' ? found([target('cart.py', 1, null, 'usage'), target('cart.py', 5, null, 'usage')], { origin: 'definition' }) : found([target('lib.py', 1, null), target('other/lib.py', 3, null)])))
    renderHarness()

    const popup = await screen.findByRole('dialog', { name: 'Definitions of price' })
    fireEvent.click(within(popup).getByRole('button', { name: /^lib\.py:1/ }))

    const modal = await screen.findByRole('dialog', { name: 'lib.py:1' })
    expect(await within(modal).findByRole('region', { name: 'Source of lib.py' })).toHaveTextContent('def price(item):')
    expect(modal.querySelector('.source-line.target')).toHaveTextContent('1def price(item):')
    expect(modal.querySelector('.hljs-keyword')).toHaveTextContent('def')
    expect(within(modal).getByRole('link', { name: 'View on GitHub' })).toHaveAttribute('href', `${GITHUB}/lib.py#L1`)
    expect(within(modal).getByRole('button', { name: 'Back' })).toBeDisabled()

    cmdClickInModal('def price(item):', 'price')
    const usages = await screen.findByRole('dialog', { name: 'Usages of price' })
    fireEvent.click(within(usages).getByRole('button', { name: /cart\.py:5/ }))

    expect(await screen.findByRole('dialog', { name: 'cart.py:5' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Back' }))
    expect(await screen.findByRole('dialog', { name: 'lib.py:1' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Back' })).toBeDisabled()

    fireEvent.click(screen.getByRole('button', { name: 'Close' }))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('opens a single definition outside the review straight in the modal', async () => {
    serve(() => found([target('lib.py', 1, null)]))
    renderHarness()

    const modal = await screen.findByRole('dialog', { name: 'lib.py:1' })
    expect(await within(modal).findByRole('region', { name: 'Source of lib.py' })).toHaveTextContent('def price(item):')
    expect(screen.queryByRole('dialog', { name: 'Definitions of price' })).not.toBeInTheDocument()
  })

  it('a single in-review target found from the modal closes it and jumps to the unit', async () => {
    serve((params) => (params.get('path') === 'lib.py' ? found([target('lib.py', 5, 4)]) : found([target('lib.py', 1, null)])))
    renderHarness()

    await screen.findByRole('dialog', { name: 'lib.py:1' })
    await screen.findAllByText((_, element) => element?.tagName === 'CODE' && element.textContent === 'def price(item):')
    cmdClickInModal('def price(item):', 'item')

    expect(await screen.findByLabelText('target')).toHaveTextContent('4:5')
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('shows a loading state while the index builds', async () => {
    let indexed = false
    let polls = 0
    serve(
      () => (indexed ? found([target('lib.py', 1, null), target('lib.py', 5, null)]) : found([], { ready: false })),
      () => {
        polls += 1
        indexed = polls > 2
        return indexed
      },
    )
    renderHarness()

    expect(await screen.findByText(/Indexing the repository/)).toBeInTheDocument()
    const popup = await screen.findByRole('dialog', { name: 'Definitions of price' }, { timeout: 2000 })
    expect(within(popup).getAllByRole('button')).toHaveLength(2)
  })

  it('says when nothing is found', async () => {
    serve(() => found([], { origin: 'definition' }))
    renderHarness()

    expect(await screen.findByText('No usages of price found.')).toBeInTheDocument()
  })

  it('shows the install hint for a missing language server once, until dismissed', async () => {
    const hint = { family: 'python', language: 'Python', install: 'uv tool install basedpyright' }
    serve(() => found([target('lib.py', 1, 4)], { server_hint: hint }))
    renderHarness()

    const note = await screen.findByRole('complementary', { name: 'Language server hint' })
    expect(note).toHaveTextContent('uv tool install basedpyright')
    fireEvent.click(within(note).getByRole('button', { name: 'Dismiss' }))
    expect(screen.queryByRole('complementary', { name: 'Language server hint' })).not.toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Cmd+click price' }))
    await screen.findByLabelText('target')
    expect(screen.queryByRole('complementary', { name: 'Language server hint' })).not.toBeInTheDocument()
  })

  it('keeps the install hint out from under the list until the list closes', async () => {
    const hint = { family: 'go', language: 'Go', install: 'go install golang.org/x/tools/gopls@latest' }
    serve(() => found([target('lib.go', 1, null), target('lib.go', 5, null)], { server_hint: hint }))
    renderHarness()

    const popup = await screen.findByRole('dialog', { name: 'Definitions of price' })
    expect(screen.queryByRole('complementary', { name: 'Language server hint' })).not.toBeInTheDocument()
    ;(popup as HTMLDialogElement).close()

    expect(await screen.findByRole('complementary', { name: 'Language server hint' })).toHaveTextContent('gopls')
  })

  it('opens the list above the pointer when there is no room below it', async () => {
    Object.defineProperty(window, 'innerHeight', { configurable: true, value: 100 })
    serve(() => found([target('lib.py', 1, null), target('lib.py', 5, null)]))
    renderHarness()

    const popup = await screen.findByRole('dialog', { name: 'Definitions of price' })
    expect(popup.style.top).toBe('auto')
    expect(popup.style.bottom).toBe('54px')
    expect(popup.style.maxHeight).toBe('38px')
    Object.defineProperty(window, 'innerHeight', { configurable: true, value: 768 })
  })

  it('fits the list on the side with more room, shrinking it to the space available', async () => {
    Object.defineProperty(window, 'innerHeight', { configurable: true, value: 140 })
    serve(() => found([target('lib.py', 1, null), target('lib.py', 5, null)]))
    renderHarness()

    const popup = await screen.findByRole('dialog', { name: 'Definitions of price' })
    expect(popup.style.top).toBe('74px')
    expect(popup.style.maxHeight).toBe('58px')
    Object.defineProperty(window, 'innerHeight', { configurable: true, value: 768 })
  })

  it('asks once per symbol whether it can navigate, keeps not-ready and failed answers briefly, and reuses the answer on click', async () => {
    vi.useFakeTimers({ toFake: ['Date'] })
    let ready = false
    const requests = serve((params) => {
      if (params.get('line') === '7') {
        throw new Error('server down')
      }
      if (params.get('column') === '4') {
        return found(ready ? [target('lib.py', 1, 4)] : [], { ready })
      }
      return found(params.get('line') === '5' ? [target('lib.py', 1, 4)] : [])
    })
    const { result } = renderHook(() => useCodeNavigation(1, 9, () => true), {
      wrapper: ({ children }) => <QueryClientProvider client={new QueryClient()}>{children}</QueryClientProvider>,
    })
    const ask = (line: number, column: number) => result.current.canNavigate({ path: 'cart.py', side: 'head', line, column })

    expect(await ask(5, 11)).toBe(true)
    expect(await ask(5, 11)).toBe(true)
    expect(await ask(6, 11)).toBe(false)
    expect(await ask(5, 4)).toBe(false)
    ready = true
    expect(await ask(5, 4)).toBe(false)
    expect(await ask(7, 11)).toBe(false)
    expect(await ask(7, 11)).toBe(false)
    vi.setSystemTime(Date.now() + UNSETTLED_ANSWER_MS)
    expect(await ask(5, 4)).toBe(true)
    expect(await ask(7, 11)).toBe(false)
    expect(await ask(5, 4)).toBe(true)

    const asked = () => requests.map((params) => `${params.get('line') ?? ''}:${params.get('column') ?? ''}`)
    expect(asked()).toEqual(['5:11', '6:11', '5:4', '7:11', '5:4', '7:11'])

    act(() => { result.current.navigate({ path: 'cart.py', side: 'head', line: 5, column: 11, point: { x: 0, y: 0 } }) })
    await waitFor(() => { expect(result.current.target).toEqual({ unitId: 4, line: 1, side: 'head' }) })
    expect(requests).toHaveLength(6)
  })

  it('closes the list on a click outside it but not on a click on its padding', async () => {
    serve(() => found([target('lib.py', 1, null), target('lib.py', 5, null)]))
    renderHarness()

    const popup = await screen.findByRole('dialog', { name: 'Definitions of price' })
    popup.getBoundingClientRect = () => DOMRect.fromRect({ x: 40, y: 74, width: 560, height: 200 })
    fireEvent.click(popup, { clientX: 45, clientY: 80 })
    expect(screen.getByRole('dialog', { name: 'Definitions of price' })).toBeInTheDocument()

    fireEvent.click(popup, { clientX: 700, clientY: 400 })
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('shows the documentation of an external name with its signature, package, version and link, rendered safely', async () => {
    const text = '```python\ndef render(request, template_name)\n```\n---\nRenders **a template**.<script>window.hacked = true</script><img src="https://example.com/x.png">\n\n![remote](https://example.com/y.png)'
    serve(() => found([], { documentation: { ...RENDER, text } }))
    renderHarness()

    const popup = await screen.findByRole('dialog', { name: 'django.shortcuts.render' })
    expect(within(popup).getByText('Django')).toBeInTheDocument()
    expect(within(popup).getByText('5.1')).toBeInTheDocument()
    expect(popup.querySelector('pre code')).toHaveTextContent('def render(request, template_name)')
    expect(within(popup).getByText('a template').tagName).toBe('STRONG')
    expect(within(popup).getByRole('link', { name: 'Documentation' })).toHaveAttribute('href', 'https://docs.djangoproject.com/')
    expect(popup.querySelector('script, img')).toBeNull()
    expect(within(popup).queryByRole('button', { name: 'Open source' })).not.toBeInTheDocument()
  })

  it('says when an external name has no documentation instead of doing nothing', async () => {
    serve(() => found([], { documentation: { ...RENDER, url: null, version: null } }))
    renderHarness()

    const popup = await screen.findByRole('dialog', { name: 'django.shortcuts.render' })
    expect(within(popup).getByText('No documentation found for django.shortcuts.render.')).toBeInTheDocument()
    expect(within(popup).getByText('Django')).toBeInTheDocument()
    expect(within(popup).queryByRole('link')).not.toBeInTheDocument()
  })

  it('opens the installed library source read only from the documentation shown inside the modal, with Back', async () => {
    serve((params) => (params.get('path') === 'lib.py' ? found([], { documentation: { ...RENDER, source: { path: SHORTCUTS, line: 1 } } }) : found([target('lib.py', 1, null)])))
    renderHarness()

    await screen.findByRole('dialog', { name: 'lib.py:1' })
    await screen.findAllByText((_, element) => element?.tagName === 'CODE' && element.textContent === 'def price(item):')
    cmdClickInModal('def price(item):', 'price')
    const popup = await screen.findByRole('dialog', { name: 'django.shortcuts.render' })
    fireEvent.click(within(popup).getByRole('button', { name: 'Open source' }))

    const library = await screen.findByRole('dialog', { name: `${SHORTCUTS}:1` })
    expect(await within(library).findByRole('region', { name: `Source of ${SHORTCUTS}` })).toHaveTextContent('def render(request, template_name):')
    expect(within(library).getByText('installed library')).toBeInTheDocument()
    expect(within(library).queryByRole('link', { name: 'View on GitHub' })).not.toBeInTheDocument()

    fireEvent.click(within(library).getByRole('button', { name: 'Back' }))
    expect(await screen.findByRole('dialog', { name: 'lib.py:1' })).toBeInTheDocument()
  })
})
