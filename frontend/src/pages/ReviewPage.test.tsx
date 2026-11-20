import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'

import type { MergeOptions, ReviewDetail, SyncResult } from '../api/types'
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
})

describe('ReviewPage merge', () => {
  beforeAll(() => {
    HTMLDialogElement.prototype.showModal = function showModal(this: HTMLDialogElement) {
      this.open = true
    }
    HTMLDialogElement.prototype.close = function close(this: HTMLDialogElement) {
      this.open = false
      this.dispatchEvent(new Event('close'))
    }
  })

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

  const STEPS = ['/api/reviews/3/forge/review', '/api/reviews/3/sync', '/api/reviews/3/sessions']

  function stubSubmit({ submit = true, sync = true, finish = true } = {}) {
    const posts: string[] = []
    vi.stubGlobal(
      'fetch',
      vi.fn((url: string, init?: RequestInit) => {
        if (init?.method === 'POST' && STEPS.includes(url)) {
          posts.push(url)
        }
        if (url === '/api/reviews/3/forge/review') {
          return submit ? Promise.resolve(Response.json({ event: 'COMMENT', published: { review_url: null, outcomes: [] }, unsent_comments: 0 })) : failure('GitHub refused the review')
        }
        if (url === '/api/reviews/3/sync') {
          return sync ? Promise.resolve(Response.json(synced)) : failure('Could not reach GitHub')
        }
        if (url === '/api/reviews/3/sessions') {
          return finish ? Promise.resolve(Response.json({})) : failure('Database is locked')
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
    renderPage()
    fireEvent.click(await screen.findByRole('button', { name: 'Submit review' }))
    const dialog = screen.getByRole('dialog', { name: 'Finish your review' })
    fireEvent.change(within(dialog).getByLabelText('Review summary (Markdown)'), { target: { value: 'Looks good' } })
    fireEvent.click(within(dialog).getByRole('button', { name: 'Submit review' }))
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
