import { describe, expect, it } from 'vitest'

import type { Comment, Thread, Unit } from '../api/types'
import {
  linkFocusFromSearch,
  resolveLinkFocus,
  withoutLinkFocus,
  type LinkFocus,
} from './linkFocus'

const THREAD_ID = '0123456789abcdef0123456789abcdef'

function unit(id: number, path: string, headStart: number | null, headEnd: number | null): Unit {
  return {
    id,
    revision_id: 1,
    path,
    old_path: null,
    module: null,
    kind: 'function',
    qualified_name: `f${String(id)}`,
    state: 'new',
    change_type: 'modified',
    base_changed: false,
    approval_id: null,
    row_approvable: false,
    rows_total: 0,
    rows_approved: 0,
    binary: false,
    image: false,
    todo: true,
    action: 'approve',
    open_threads: 0,
    head_start: headStart,
    head_end: headEnd,
  }
}

function comment(remoteUrl: string | null): Comment {
  return {
    id: 'c',
    thread_id: 't',
    author: { id: 1, email: 'a@b.c', name: 'A' },
    body: 'hi',
    created_at: '',
    edited_at: null,
    deleted: false,
    mine: false,
    remote_url: remoteUrl,
  }
}

function thread(id: string, unitId: number | null, remoteUrl: string | null = null, scope: Thread['scope'] = 'unit'): Thread {
  return {
    id,
    scope,
    path: 'src/app.py',
    module: null,
    kind: 'function',
    qualified_name: 'f',
    side: 'head',
    status: 'open',
    resolvable: true,
    created_by: { id: 1, email: 'a@b.c', name: 'A' },
    created_at: '',
    line_text: null,
    line_count: 1,
    context_before: [],
    context_after: [],
    anchor: scope === 'unit' ? { revision_id: 1, line_offset: 0, outdated: unitId === null, unit_id: unitId, file_line: 4, end_file_line: 4 } : null,
    comments: [comment(remoteUrl)],
    can_delete: false,
  }
}

const focus = (values: Partial<LinkFocus>): LinkFocus => ({ path: null, line: null, thread: null, comment: null, ...values })
const units = [unit(1, 'src/app.py', 1, 9), unit(2, 'src/app.py', 12, 30), unit(3, 'README.md', null, null)]

describe('linkFocusFromSearch', () => {
  it('reads the focus of a link', () => {
    const search = `?path=src%2Fapp.py&line=42&thread=${THREAD_ID}&comment=501`

    expect(linkFocusFromSearch(search)).toEqual({ path: 'src/app.py', line: 42, thread: THREAD_ID, comment: '501' })
  })

  it('keeps only a positive line of a path and returns null without a focus', () => {
    expect(linkFocusFromSearch('')).toBeNull()
    expect(linkFocusFromSearch('?line=4')).toBeNull()
    expect(linkFocusFromSearch('?path=a.py&line=0')).toEqual(focus({ path: 'a.py' }))
    expect(linkFocusFromSearch('?path=a.py&line=4x')).toEqual(focus({ path: 'a.py' }))
  })
})

describe('withoutLinkFocus', () => {
  it('drops only the link parameters', () => {
    expect(withoutLinkFocus('?path=a.py&line=2&thread=t&comment=1')).toBe('')
    expect(withoutLinkFocus('?path=a.py&view=split')).toBe('?view=split')
    expect(withoutLinkFocus('')).toBe('')
  })
})

describe('resolveLinkFocus', () => {
  it('picks the unit of the file that contains the line', () => {
    expect(resolveLinkFocus(focus({ path: 'src/app.py', line: 20 }), units, [])).toEqual({ unitId: 2, elementId: 'unit-2' })
  })

  it('picks the narrowest unit when a module or class contains the unit of the line', () => {
    const nested = [unit(4, 'app.py', 1, 40), unit(5, 'app.py', 5, 35), unit(6, 'app.py', 20, 30)]

    expect(resolveLinkFocus(focus({ path: 'app.py', line: 25 }), nested, [])?.unitId).toBe(6)
    expect(resolveLinkFocus(focus({ path: 'app.py', line: 10 }), nested, [])?.unitId).toBe(5)
    expect(resolveLinkFocus(focus({ path: 'app.py', line: 38 }), nested, [])?.unitId).toBe(4)
  })

  it('picks the unit nearest to a line that no unit contains', () => {
    expect(resolveLinkFocus(focus({ path: 'src/app.py', line: 11 }), units, [])?.unitId).toBe(2)
    expect(resolveLinkFocus(focus({ path: 'src/app.py', line: 10 }), units, [])?.unitId).toBe(1)
    expect(resolveLinkFocus(focus({ path: 'src/app.py', line: 500 }), units, [])?.unitId).toBe(2)
  })

  it('falls back to the first unit of the file', () => {
    expect(resolveLinkFocus(focus({ path: 'src/app.py' }), units, [])?.unitId).toBe(1)
    expect(resolveLinkFocus(focus({ path: 'README.md', line: 3 }), units, [])?.unitId).toBe(3)
    expect(resolveLinkFocus(focus({ path: 'missing.py' }), units, [])).toBeNull()
  })

  it('focuses an inline thread inside its unit', () => {
    const target = resolveLinkFocus(focus({ thread: THREAD_ID }), units, [thread(THREAD_ID, 2)])

    expect(target).toEqual({ unitId: 2, elementId: `thread-${THREAD_ID}` })
  })

  it('opens the conversation panel for threads that are not shown in a unit', () => {
    expect(resolveLinkFocus(focus({ thread: THREAD_ID }), units, [thread(THREAD_ID, null)])).toEqual({ unitId: null, elementId: `thread-${THREAD_ID}` })
    expect(resolveLinkFocus(focus({ thread: THREAD_ID }), units, [thread(THREAD_ID, null, null, 'file')])?.unitId).toBeNull()
  })

  it('finds the imported thread of a GitHub discussion anchor', () => {
    const threads = [thread('a', 1, 'https://github.com/acme/widgets/pull/7#discussion_r5010'), thread('b', 2, 'https://github.com/acme/widgets/pull/7#discussion_r501')]

    expect(resolveLinkFocus(focus({ comment: '501' }), units, threads)?.elementId).toBe('thread-b')
    expect(resolveLinkFocus(focus({ comment: '77' }), units, [thread('c', 1, 'https://github.com/acme/widgets/pull/7#issuecomment-77', 'review')])?.elementId).toBe('thread-c')
  })

  it('uses the path when an inline thread belongs to a unit that is not listed', () => {
    expect(resolveLinkFocus(focus({ thread: THREAD_ID, path: 'README.md' }), units, [thread(THREAD_ID, 99)])?.unitId).toBe(3)
    expect(resolveLinkFocus(focus({ thread: THREAD_ID }), units, [thread(THREAD_ID, 99)])).toBeNull()
  })

  it('falls back to the comment when the thread id is unknown', () => {
    const threads = [thread('b', 2, 'https://github.com/acme/widgets/pull/7#discussion_r501')]

    expect(resolveLinkFocus(focus({ thread: THREAD_ID, comment: '501' }), units, threads)?.elementId).toBe('thread-b')
  })

  it('uses the path when the thread is unknown', () => {
    expect(resolveLinkFocus(focus({ comment: '9', path: 'README.md' }), units, [])?.unitId).toBe(3)
    expect(resolveLinkFocus(focus({ comment: '9' }), units, [])).toBeNull()
  })
})
