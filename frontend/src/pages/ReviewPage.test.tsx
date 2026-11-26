import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'

import type { SourceFile } from '../api/navigation'
import type { AiChatMessage, MergeOptions, ReviewDetail, SyncResult, Unit, UnitDiff } from '../api/types'
import type { PendingLink } from '../review/linkFocus'
import { ReviewPage, type ReviewExtensions } from './ReviewPage'

const revision = { id: 2, number: 1, head_sha: 'b', base_sha: 'a', merge_base_sha: 'a', created_at: '2026-11-04T10:00:00Z' }

function reviewWithTitle(title: string): ReviewDetail {
  return {
    id: 3,
    repo_id: 1,
    repo_name: 'bussola',
    head_ref: 'refs/bussola/pull/34',
    base_ref: 'origin/main',
    latest_revision: revision,
    counts: { approved: 0, approved_moved: 0, changed: 0, partial: 0, removed: 0, new: 0 },
    total: 0,
    approved: 0,
    open_threads: 0,
    total_threads: 0,
    last_session_at: null,
    pull_request: { number: 34, title, url: null, author: null, state: 'OPEN', description: null },
    pull_request_review: true,
    unsent_comments: 0,
  }
}

function renderPage(extensions?: ReviewExtensions) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <ReviewPage reviewId={3} extensions={extensions} />
    </QueryClientProvider>,
  )
}

const synced: SyncResult = {
  refresh: { revision, created: false, warning: null },
  published: null,
  publish_error: null,
  unsent_comments: 0,
  marked_viewed: [],
  not_viewed: {},
  viewed_error: null,
}

function stubServer() {
  let title = 'feat: first title'
  vi.stubGlobal(
    'fetch',
    vi.fn((url: string) => {
      if (url === '/api/reviews/3/sync') {
        title = 'feat: renamed on GitHub'
        return Promise.resolve(Response.json(synced))
      }
      if (url === '/api/reviews/3/forge/sync') {
        return Promise.resolve(Response.json({ changes: 0, new_commits: false, state: 'OPEN' }))
      }
      return Promise.resolve(Response.json(url === '/api/reviews/3' ? reviewWithTitle(title) : []))
    }),
  )
}

beforeAll(() => {
  HTMLDialogElement.prototype.showModal = function showModal(this: HTMLDialogElement) {
    this.open = true
  }
  HTMLDialogElement.prototype.close = function close(this: HTMLDialogElement) {
    this.open = false
    this.dispatchEvent(new Event('close'))
  }
})

describe('ReviewPage window title', () => {
  beforeEach(() => {
    document.title = 'bussola'
    stubServer()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('names the pull request, follows its title after a sync and goes back to the default when left', async () => {
    const { unmount } = renderPage()

    await waitFor(() => {
      expect(document.title).toBe('bussola#34 feat: first title')
    })

    fireEvent.click(screen.getByRole('button', { name: 'Sync' }))

    await waitFor(() => {
      expect(document.title).toBe('bussola#34 feat: renamed on GitHub')
    })

    unmount()

    expect(document.title).toBe('bussola')
  })
})

describe('ReviewPage conversation panel', () => {
  const extensions: ReviewExtensions = { sidePanel: { label: 'conversation', count: 2, content: <><p>Thread list</p><textarea aria-label="Review comment" /></> } }

  beforeEach(() => {
    window.localStorage.clear()
    stubServer()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('hides the panel behind a thin bar with the open count and remembers it after a reload', async () => {
    window.localStorage.setItem('bussola.sidePanelHidden', 'false')
    const { unmount } = renderPage(extensions)

    expect(await screen.findByText('Thread list')).toBeVisible()

    fireEvent.click(screen.getByRole('button', { name: 'Hide conversation' }))

    expect(screen.getByText('Thread list')).not.toBeVisible()
    const reopen = screen.getByRole('button', { name: 'Show conversation (2 open)' })
    expect(reopen).toHaveAttribute('aria-expanded', 'false')
    expect(reopen).toHaveTextContent('2')
    expect(window.localStorage.getItem('bussola.sidePanelHidden')).toBe('true')

    unmount()
    renderPage(extensions)

    expect(await screen.findByRole('button', { name: 'Show conversation (2 open)' })).toBeInTheDocument()
    expect(screen.getByText('Thread list')).not.toBeVisible()

    fireEvent.click(screen.getByRole('button', { name: 'Show conversation (2 open)' }))

    expect(screen.getByText('Thread list')).toBeVisible()
    expect(window.localStorage.getItem('bussola.sidePanelHidden')).toBe('false')
  })

  it('draws the conversation toggle as a right column and the files toggle as a left one', async () => {
    window.localStorage.setItem('bussola.sidePanelHidden', 'true')
    renderPage(extensions)
    const divider = (button: HTMLElement) => button.querySelector('path')?.getAttribute('d')

    expect(divider(await screen.findByRole('button', { name: 'Show conversation (2 open)' }))).toBe('M10 2.5v11')
    expect(divider(screen.getByRole('button', { name: 'Files' }))).toBe('M6 2.5v11')
  })

  it('keeps an unsent comment while the panel is hidden', async () => {
    window.localStorage.setItem('bussola.sidePanelHidden', 'false')
    renderPage(extensions)
    fireEvent.change(await screen.findByRole('textbox', { name: 'Review comment' }), { target: { value: 'Not sent yet' } })

    fireEvent.click(screen.getByRole('button', { name: 'Hide conversation' }))
    fireEvent.click(screen.getByRole('button', { name: 'Show conversation (2 open)' }))

    expect(screen.getByRole('textbox', { name: 'Review comment' })).toHaveValue('Not sent yet')
  })

  it('toggles the panel with t, but not while typing', async () => {
    window.localStorage.setItem('bussola.sidePanelHidden', 'true')
    renderPage(extensions)
    await screen.findByRole('button', { name: 'Show conversation (2 open)' })

    fireEvent.keyDown(screen.getByRole('searchbox'), { key: 't' })
    expect(screen.getByText('Thread list')).not.toBeVisible()

    fireEvent.keyDown(window, { key: 't' })
    expect(screen.getByText('Thread list')).toBeVisible()
    expect(window.localStorage.getItem('bussola.sidePanelHidden')).toBe('false')

    fireEvent.keyDown(window, { key: 't' })
    expect(screen.getByText('Thread list')).not.toBeVisible()
    expect(window.localStorage.getItem('bussola.sidePanelHidden')).toBe('true')
  })

  it('opens the panel in a full-height window and closes it with Esc, the close button or the backdrop, giving focus back to the control', async () => {
    window.localStorage.setItem('bussola.sidePanelHidden', 'false')
    renderPage(extensions)
    await screen.findByRole('button', { name: 'Expand conversation' })
    const closeWays = [
      () => { fireEvent.keyDown(screen.getByRole('button', { name: 'Close' }), { key: 'Escape' }) },
      () => { fireEvent.click(screen.getByRole('button', { name: 'Close' })) },
      () => {
        const backdrop = document.querySelector('.side-panel-backdrop')
        if (backdrop) {
          fireEvent.click(backdrop)
        }
      },
    ]

    for (const close of closeWays) {
      fireEvent.click(screen.getByRole('button', { name: 'Expand conversation' }))

      const dialog = screen.getByRole('dialog', { name: 'conversation' })
      expect(dialog).toHaveAttribute('aria-modal', 'true')
      expect(within(dialog).getByText('Thread list')).toBeVisible()
      expect(within(dialog).getByRole('button', { name: 'Close' })).toHaveFocus()
      expect(screen.queryByRole('button', { name: 'Hide conversation' })).not.toBeInTheDocument()

      close()

      expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Expand conversation' })).toHaveFocus()
      expect(screen.getByText('Thread list')).toBeVisible()
    }
  })

  it('keeps the keyboard focus inside the window while it is open, and t closes it', async () => {
    window.localStorage.setItem('bussola.sidePanelHidden', 'false')
    renderPage(extensions)
    fireEvent.click(await screen.findByRole('button', { name: 'Expand conversation' }))
    const close = screen.getByRole('button', { name: 'Close' })
    const comment = screen.getByRole('textbox', { name: 'Review comment' })

    comment.focus()
    fireEvent.keyDown(comment, { key: 'Tab' })
    expect(close).toHaveFocus()

    fireEvent.keyDown(close, { key: 'Tab', shiftKey: true })
    expect(comment).toHaveFocus()

    screen.getByRole('searchbox').focus()
    expect(close).toHaveFocus()

    fireEvent.keyDown(window, { key: 'r' })
    await new Promise((resolve) => setTimeout(resolve, 0))
    expect(vi.mocked(fetch).mock.calls.some(([url]) => url === '/api/reviews/3/sync')).toBe(false)

    fireEvent.keyDown(window, { key: 't' })
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(screen.getByText('Thread list')).toBeVisible()
    expect(window.localStorage.getItem('bussola.sidePanelHidden')).toBe('false')
  })

  it('keeps what is in the panel when it moves to the window and back, and Esc in a text field leaves it open', async () => {
    window.localStorage.setItem('bussola.sidePanelHidden', 'false')
    renderPage(extensions)
    const comment = await screen.findByRole('textbox', { name: 'Review comment' })
    fireEvent.change(comment, { target: { value: 'Not sent yet' } })

    fireEvent.click(screen.getByRole('button', { name: 'Expand conversation' }))
    expect(within(screen.getByRole('dialog')).getByRole('textbox', { name: 'Review comment' })).toBe(comment)

    fireEvent.keyDown(comment, { key: 'Escape' })
    expect(screen.getByRole('dialog')).toBeInTheDocument()

    fireEvent.change(comment, { target: { value: 'Not sent yet, longer' } })
    fireEvent.click(screen.getByRole('button', { name: 'Close' }))

    expect(screen.getByRole('textbox', { name: 'Review comment' })).toBe(comment)
    expect(comment).toHaveValue('Not sent yet, longer')
  })

  it('closes the window when a link shows code in the review, and keeps it for a thread of the panel', async () => {
    window.localStorage.setItem('bussola.sidePanelHidden', 'false')
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    const page = (link?: PendingLink) => (
      <QueryClientProvider client={client}>
        <ReviewPage reviewId={3} extensions={{ ...extensions, link }} />
      </QueryClientProvider>
    )
    const { rerender } = render(page())
    fireEvent.click(await screen.findByRole('button', { name: 'Expand conversation' }))

    rerender(page({ key: 'thread', ready: true, resolve: () => ({ unitId: null, elementId: 'thread-1' }) }))
    expect(screen.getByRole('dialog', { name: 'conversation' })).toBeInTheDocument()

    rerender(page({ key: 'code', ready: true, resolve: () => ({ unitId: 7, elementId: 'unit-7' }) }))
    await waitFor(() => { expect(screen.queryByRole('dialog')).not.toBeInTheDocument() })
    expect(screen.getByText('Thread list')).toBeVisible()
  })

  it('offers the window only while the panel is shown', async () => {
    window.localStorage.setItem('bussola.sidePanelHidden', 'true')
    renderPage(extensions)
    await screen.findByRole('button', { name: 'Show conversation (2 open)' })

    expect(screen.queryByRole('button', { name: 'Expand conversation' })).not.toBeInTheDocument()
  })
})

describe('ReviewPage merge', () => {
  beforeEach(() => {
    let state = 'OPEN'
    const options: MergeOptions = {
      head_sha: 'b',
      methods: ['squash'],
      default_method: 'squash',
      commit_texts: { squash: { title: 'feat: first title (#34)', message: '' } },
      blockers: [],
      branch_deletion: 'optional',
    }
    vi.stubGlobal(
      'fetch',
      vi.fn((url: string, init?: RequestInit) => {
        if (url === '/api/reviews/3/forge/merge') {
          if (init?.method === 'POST') {
            state = 'MERGED'
            return Promise.resolve(Response.json({ state, branch_deleted: false, branch_error: null }))
          }
          return Promise.resolve(Response.json(options))
        }
        if (url === '/api/reviews/3') {
          const review = reviewWithTitle('feat: first title')
          return Promise.resolve(Response.json({ ...review, pull_request: review.pull_request && { ...review.pull_request, state } }))
        }
        return Promise.resolve(Response.json([]))
      }),
    )
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('opens the merge options in a dialog and shows the result in the header after merging', async () => {
    renderPage()

    fireEvent.click(await screen.findByRole('button', { name: 'Merge' }))
    const dialog = screen.getByRole('dialog', { name: 'Merge pull request' })
    expect(dialog).toHaveAttribute('open')
    expect(await within(dialog).findByLabelText('Commit title')).toHaveValue('feat: first title (#34)')

    fireEvent.click(within(dialog).getByRole('button', { name: 'Merge' }))

    expect(await screen.findByText('Pull request merged.')).toBeInTheDocument()
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    await waitFor(() => { expect(screen.queryByRole('button', { name: 'Merge' })).not.toBeInTheDocument() })
  })
})

describe('ReviewPage submit review', () => {
  const failure = (detail: string) => Promise.resolve(Response.json({ detail }, { status: 502 }))

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  const STEPS = ['/api/reviews/3/forge/review', '/api/reviews/3/sync', '/api/reviews/3/sessions']

  function stubSubmit({ submit = true, sync = true, finish = true, syncBody = synced, syncGate = Promise.resolve() } = {}) {
    const posts: string[] = []
    const answers: Record<string, [boolean, unknown, string]> = {
      [STEPS[0]]: [submit, { event: 'COMMENT', published: { review_url: null, outcomes: [] }, unsent_comments: 0 }, 'GitHub refused the review'],
      [STEPS[1]]: [sync, syncBody, 'Could not reach GitHub'],
      [STEPS[2]]: [finish, {}, 'Database is locked'],
    }
    vi.stubGlobal(
      'fetch',
      vi.fn((url: string) => {
        if (url in answers) {
          posts.push(url)
          const [ok, body, error] = answers[url]
          const answer = () => (ok ? Promise.resolve(Response.json(body)) : failure(error))
          return url === STEPS[1] ? syncGate.then(answer) : answer()
        }
        if (url === '/api/reviews/3/forge/sync') {
          return Promise.resolve(Response.json({ changes: 0, new_commits: false, state: 'OPEN' }))
        }
        return Promise.resolve(Response.json(url === '/api/reviews/3' ? reviewWithTitle('feat: first title') : []))
      }),
    )
    return posts
  }

  async function submitReview() {
    const page = renderPage()
    fireEvent.click(await screen.findByRole('button', { name: 'Submit review' }))
    const dialog = screen.getByRole('dialog', { name: 'Finish your review' })
    fireEvent.change(within(dialog).getByLabelText('Review summary (Markdown)'), { target: { value: 'Looks good' } })
    fireEvent.click(within(dialog).getByRole('button', { name: 'Submit review' }))
    return page
  }

  it('syncs and marks as reviewed after submitting, sending the review once', async () => {
    const posts = stubSubmit()

    await submitReview()

    expect(await screen.findByText('Synced and marked as reviewed.', { exact: false })).toBeInTheDocument()
    expect(posts).toEqual(STEPS)
  })

  it('does not mark as reviewed when the sync fails', async () => {
    const posts = stubSubmit({ sync: false })

    await submitReview()

    expect(await screen.findByText('Sync failed, so it was not marked as reviewed', { exact: false })).toBeInTheDocument()
    expect(screen.getByText('Could not reach GitHub')).toBeInTheDocument()
    expect(posts).toEqual(STEPS.slice(0, 2))
  })

  it('does not mark as reviewed when the sync could only check the local branch', async () => {
    const posts = stubSubmit({ syncBody: { ...synced, refresh: { ...synced.refresh, warning: 'Could not fetch (offline). Checked the local branch instead.' } } })

    await submitReview()

    expect(await screen.findByText('Sync failed, so it was not marked as reviewed', { exact: false })).toBeInTheDocument()
    expect(screen.getByText('Could not fetch (offline)', { exact: false })).toBeInTheDocument()
    expect(posts).toEqual(STEPS.slice(0, 2))
  })

  it('still marks as reviewed when the page is left during the sync', async () => {
    let openGate: () => void = () => undefined
    const posts = stubSubmit({ syncGate: new Promise<void>((done) => { openGate = done }) })

    const { unmount } = await submitReview()
    await waitFor(() => { expect(posts).toEqual(STEPS.slice(0, 2)) })
    unmount()
    openGate()

    await waitFor(() => { expect(posts).toEqual(STEPS) })
  })

  it('says when marking as reviewed fails after the sync', async () => {
    stubSubmit({ finish: false })

    await submitReview()

    expect(await screen.findByText('Synced, but Mark as reviewed failed', { exact: false })).toBeInTheDocument()
    expect(screen.getByText('Database is locked')).toBeInTheDocument()
  })

  it('neither syncs nor marks as reviewed when the submit fails', async () => {
    const posts = stubSubmit({ submit: false })

    await submitReview()

    expect(await screen.findByText('GitHub refused the review')).toBeInTheDocument()
    expect(posts).toEqual(STEPS.slice(0, 1))
  })
})

describe('ReviewPage code navigation', () => {
  const unit: Unit = {
    id: 7,
    revision_id: 2,
    path: 'app.py',
    old_path: null,
    module: 'app',
    kind: 'function',
    qualified_name: 'total',
    state: 'approved',
    change_type: 'modified',
    base_changed: false,
    approval_id: 'a1',
    row_approvable: true,
    rows_total: 2,
    rows_approved: 2,
    binary: false,
    image: false,
    todo: false,
    action: 'revoke',
    open_threads: 0,
    head_start: 1,
    head_end: 2,
  }
  const diff: UnitDiff = { unit_id: 7, mode: 'base', available_modes: ['base'], approved_text_unavailable: false, binary: false, unified: '', rows: [] }
  const answer = (unitId: number): AiChatMessage => ({
    id: 1,
    role: 'assistant',
    body: 'See [the total](#after:app.py:2).',
    snippets: [],
    lookups: [],
    comments: [],
    links: [{ path: 'app.py', side: 'head', line: 2, unit_id: unitId }],
    provider_label: null,
    model: null,
    effort: null,
    created_at: '2026-11-09T10:00:05Z',
  })
  const source: SourceFile = { path: 'app.py', side: 'head', commit: 'b', text: 'def total(items):\n    return sum(items)\n', url: null }

  function serve({ toReview, linkedUnitId }: { toReview: Unit[]; linkedUnitId: number }) {
    vi.stubGlobal(
      'fetch',
      vi.fn((url: string) => {
        if (url === '/api/reviews/3') {
          return Promise.resolve(Response.json(reviewWithTitle('feat: totals')))
        }
        if (url.startsWith('/api/reviews/3/units?')) {
          return Promise.resolve(Response.json(url.includes('filter=all') ? [unit] : toReview))
        }
        if (url.startsWith('/api/reviews/3/units/7/diff')) {
          return Promise.resolve(Response.json(diff))
        }
        if (url.startsWith('/api/reviews/3/source?')) {
          return Promise.resolve(Response.json(source))
        }
        return Promise.resolve(Response.json(url === '/api/reviews/3/ai-chat' ? [answer(linkedUnitId)] : []))
      }),
    )
  }

  async function searchFor(text: string) {
    renderPage({ sidePanel: { label: 'conversation', count: 0, content: null } })
    const search = await screen.findByRole('searchbox', { name: 'Find units by module, name or path' })
    fireEvent.change(search, { target: { value: text } })
    expect(screen.getByRole('tab', { name: 'To review' })).toHaveAttribute('aria-selected', 'true')
    return search
  }

  beforeEach(() => {
    window.localStorage.setItem('bussola.unitFilter', 'todo')
    window.localStorage.setItem('bussola.sidePanelTab', 'chat')
    window.localStorage.setItem('bussola.sidePanelHidden', 'false')
    Element.prototype.scrollIntoView = vi.fn()
  })

  afterEach(() => {
    window.localStorage.clear()
    vi.unstubAllGlobals()
  })

  it('shows every unit when a line of the review hidden by the view is opened, and focuses its unit', async () => {
    serve({ toReview: [], linkedUnitId: 7 })
    const search = await searchFor('nothing matches')

    fireEvent.click(await screen.findByText('the total'))

    await waitFor(() => { expect(screen.getByRole('tab', { name: 'All' })).toHaveAttribute('aria-selected', 'true') })
    expect(search).toHaveValue('')
    await waitFor(() => { expect(document.getElementById('unit-7')).toHaveClass('focused') })
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('keeps the view when the unit of the line is already shown', async () => {
    serve({ toReview: [{ ...unit, state: 'changed', todo: true, action: 'approve' }], linkedUnitId: 7 })
    const search = await searchFor('total')

    fireEvent.click(await screen.findByText('the total'))

    await waitFor(() => { expect(document.getElementById('unit-7')).toHaveClass('focused') })
    expect(screen.getByRole('tab', { name: 'To review' })).toHaveAttribute('aria-selected', 'true')
    expect(search).toHaveValue('total')
  })

  it('opens the source of a line whose unit is not in the reviewed revision and keeps the view', async () => {
    serve({ toReview: [], linkedUnitId: 99 })
    const search = await searchFor('nothing matches')

    fireEvent.click(await screen.findByText('the total'))

    const modal = await screen.findByRole('dialog', { name: 'app.py:2' })
    expect(await within(modal).findByRole('region', { name: 'Source of app.py' })).toHaveTextContent('def total(items):')
    expect(screen.getByRole('tab', { name: 'To review' })).toHaveAttribute('aria-selected', 'true')
    expect(search).toHaveValue('nothing matches')
  })
})
