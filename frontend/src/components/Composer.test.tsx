import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { useKeyboardShortcuts } from '../hooks/useKeyboardShortcuts'
import { Composer } from './Composer'

const MODE_KEY = 'bussola.commentEditor'
const IMAGE_URL = `/api/attachments/${'a'.repeat(64)}.png`

interface Deferred {
  promise: Promise<Response>
  resolve: (response: Response) => void
}

function deferred(): Deferred {
  let resolve: (response: Response) => void = () => undefined
  const promise = new Promise<Response>((done) => {
    resolve = done
  })
  return { promise, resolve }
}

function uploaded(): Promise<Response> {
  return Promise.resolve(Response.json({ url: IMAGE_URL }, { status: 201 }))
}

function stubApi(people: string[], upload: () => Promise<Response> = uploaded) {
  const fetchMock = vi.fn((url: string) => (url.endsWith('/mentions') ? Promise.resolve(Response.json(people)) : upload()))
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

function Shortcuts({ onKey }: { onKey: () => void }) {
  useKeyboardShortcuts({ j: onKey })
  return null
}

function renderComposer(props: { initial?: string; onSubmit?: (body: string) => void; onCancel?: () => void } = {}) {
  const onSubmit = vi.fn(props.onSubmit)
  const onKey = vi.fn()
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <Shortcuts onKey={onKey} />
      <Composer reviewId={3} submitLabel="Comment" placeholder="Comment" initial={props.initial} onSubmit={onSubmit} onCancel={props.onCancel} />
    </QueryClientProvider>,
  )
  return { onSubmit, onKey }
}

function textarea(): HTMLTextAreaElement {
  return screen.getByRole<HTMLTextAreaElement>('textbox', { name: 'Comment' })
}

function richEditor(): HTMLElement {
  return screen.getByRole('textbox', { name: 'Comment' })
}

function type(value: string) {
  const element = textarea()
  fireEvent.change(element, { target: { value } })
  element.setSelectionRange(value.length, value.length)
  fireEvent.select(element)
}

function attach(file: File) {
  const input = screen.getByLabelText<HTMLInputElement>('Attach image')
  fireEvent.change(input, { target: { files: [file] } })
}

const png = (name = 'shot.png') => new File(['png'], name, { type: 'image/png' })

beforeEach(() => {
  window.localStorage.clear()
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('Composer mentions', () => {
  it('suggests people as you type and inserts the chosen one', async () => {
    const fetchMock = stubApi(['bob', 'carol', 'caroline', 'dave'])
    renderComposer()

    type('Thanks @car')
    const options = await screen.findAllByRole('option')
    expect(options.map((option) => option.textContent)).toEqual(['@carol', '@caroline'])
    expect(fetchMock).toHaveBeenCalledWith('/api/reviews/3/mentions', expect.anything())

    fireEvent.keyDown(textarea(), { key: 'ArrowDown' })
    expect(screen.getByRole('option', { selected: true })).toHaveTextContent('@caroline')
    fireEvent.keyDown(textarea(), { key: 'Enter' })

    expect(textarea()).toHaveValue('Thanks @caroline ')
    expect(screen.queryByRole('listbox')).toBeNull()
  })

  it('closes the list with Escape without cancelling the comment', async () => {
    stubApi(['bob'])
    const onCancel = vi.fn()
    renderComposer({ onCancel })

    type('@')
    await screen.findByRole('listbox')
    fireEvent.keyDown(textarea(), { key: 'Escape' })

    expect(screen.queryByRole('listbox')).toBeNull()
    expect(onCancel).not.toHaveBeenCalled()
    expect(textarea()).toHaveValue('@')
  })

  it('shows no list when the review has nobody to mention', async () => {
    const fetchMock = stubApi([])
    renderComposer()

    type('@b')
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalled()
    })

    expect(screen.queryByRole('listbox')).toBeNull()
  })
})

describe('Composer image upload', () => {
  it('shows a placeholder while the image is uploaded, then a Markdown image', async () => {
    const upload = deferred()
    const fetchMock = stubApi([], () => upload.promise)
    renderComposer()
    type('Look: ')

    attach(png())

    expect(textarea()).toHaveValue('Look: ![Uploading shot.png...]()')
    expect(fetchMock).toHaveBeenCalledWith('/api/attachments', expect.objectContaining({ method: 'POST', headers: { 'Content-Type': 'image/png' } }))
    await act(async () => {
      upload.resolve(Response.json({ url: IMAGE_URL }, { status: 201 }))
      await upload.promise
    })
    await waitFor(() => {
      expect(textarea()).toHaveValue(`Look: ![shot.png](${IMAGE_URL})`)
    })
  })

  it('uploads pasted and dropped images', async () => {
    stubApi([])
    renderComposer()

    fireEvent.paste(textarea(), { clipboardData: { files: [png('pasted.png')] } })
    await waitFor(() => {
      expect(textarea()).toHaveValue(`![pasted.png](${IMAGE_URL})`)
    })
    fireEvent.drop(textarea(), { dataTransfer: { files: [png('dropped.png')] } })

    await waitFor(() => {
      expect(textarea().value).toContain(`![dropped.png](${IMAGE_URL})`)
    })
  })

  it('refuses files that are not supported images', () => {
    const fetchMock = stubApi([])
    renderComposer()

    attach(new File(['<svg/>'], 'logo.svg', { type: 'image/svg+xml' }))
    attach(new File([new Uint8Array(11 * 1024 * 1024)], 'huge.png', { type: 'image/png' }))

    expect(screen.getByRole('alert')).toHaveTextContent('huge.png cannot be attached: images can be at most 10 MB.')
    expect(fetchMock).not.toHaveBeenCalled()
    expect(textarea()).toHaveValue('')
  })

  it('removes the placeholder and explains a failed upload', async () => {
    stubApi([], () => Promise.resolve(Response.json({ detail: 'Only PNG, JPEG, GIF and WebP images can be attached' }, { status: 400 })))
    renderComposer()

    attach(png())

    expect(await screen.findByRole('alert')).toHaveTextContent('shot.png could not be uploaded: Only PNG, JPEG, GIF and WebP images can be attached')
    expect(textarea()).toHaveValue('')
  })
})

describe('Composer rich text mode', () => {
  it('shows formatting and gives back the exact Markdown when nothing was edited', () => {
    stubApi([])
    const markdown = '* **bold** item\n\n```mermaid\ngraph TD\n```'
    renderComposer({ initial: markdown })

    fireEvent.click(screen.getByRole('tab', { name: 'Rich text' }))
    expect(richEditor().querySelector('strong')).toHaveTextContent('bold')
    expect(window.localStorage.getItem(MODE_KEY)).toBe('rich')
    fireEvent.click(screen.getByRole('tab', { name: 'Write' }))

    expect(textarea()).toHaveValue(markdown)
    expect(window.localStorage.getItem(MODE_KEY)).toBe('write')
  })

  it('opens in the mode kept in the browser and sends Markdown', () => {
    stubApi([])
    window.localStorage.setItem(MODE_KEY, 'rich')
    const { onSubmit } = renderComposer({ initial: 'Hello' })

    const editor = richEditor()
    editor.innerHTML = '<p>Hello <strong>world</strong></p>'
    fireEvent.input(editor)
    fireEvent.click(screen.getByRole('button', { name: 'Comment' }))

    expect(onSubmit).toHaveBeenCalledWith('Hello **world**', expect.any(Function))
  })

  it('stays in Write mode for Markdown it cannot keep', () => {
    stubApi([])
    renderComposer({ initial: 'a&nbsp;b' })

    fireEvent.click(screen.getByRole('tab', { name: 'Rich text' }))

    expect(screen.getByRole('alert')).toHaveTextContent('stays in Write mode')
    expect(textarea()).toHaveValue('a&nbsp;b')
  })

  it('opens in Write mode with a note when the kept mode cannot show the comment', () => {
    stubApi([])
    window.localStorage.setItem(MODE_KEY, 'rich')
    renderComposer({ initial: 'a&nbsp;b' })

    expect(screen.getByRole('alert')).toHaveTextContent('stays in Write mode')
    expect(textarea()).toHaveValue('a&nbsp;b')
  })

  it('uploads images into the rich text', async () => {
    const upload = deferred()
    stubApi([], () => upload.promise)
    window.localStorage.setItem(MODE_KEY, 'rich')
    const { onSubmit } = renderComposer({ initial: 'Look' })

    attach(png())
    expect(richEditor().querySelector('img')).toHaveAttribute('alt', 'Uploading shot.png...')
    await act(async () => {
      upload.resolve(Response.json({ url: IMAGE_URL }, { status: 201 }))
      await upload.promise
    })
    await waitFor(() => {
      expect(richEditor().querySelector('img')).toHaveAttribute('src', IMAGE_URL)
    })
    fireEvent.click(screen.getByRole('button', { name: 'Comment' }))

    expect(onSubmit).toHaveBeenCalledWith(`Look![shot.png](${IMAGE_URL})`, expect.any(Function))
  })

  it('suggests mentions in rich text', async () => {
    stubApi(['carol'])
    window.localStorage.setItem(MODE_KEY, 'rich')
    renderComposer({ initial: 'Hi @ca' })

    const editor = richEditor()
    const text = editor.querySelector('p')?.firstChild
    if (!text) {
      throw new Error('no text')
    }
    window.getSelection()?.collapse(text, 6)
    fireEvent.keyUp(editor, { key: 'a' })
    fireEvent.mouseDown(await screen.findByRole('option', { name: '@carol' }))

    expect(editor.textContent).toBe('Hi @carol ')
  })

  it('keeps review shortcuts disabled while typing in either mode', () => {
    stubApi([])
    const { onKey } = renderComposer()

    fireEvent.keyDown(textarea(), { key: 'j' })
    fireEvent.click(screen.getByRole('tab', { name: 'Rich text' }))
    fireEvent.keyDown(richEditor(), { key: 'j' })
    fireEvent.keyDown(document.body, { key: 'j' })

    expect(onKey).toHaveBeenCalledTimes(1)
  })
})
