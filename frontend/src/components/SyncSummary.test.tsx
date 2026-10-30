import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import type { SyncResult } from '../api/types'
import { SyncSummary } from './SyncSummary'

const revision = { id: 2, number: 2, head_sha: 'b', base_sha: 'a', merge_base_sha: 'a', created_at: '2026-10-28T10:00:00Z' }

describe('SyncSummary', () => {
  it('lists the files that could not be marked as viewed as errors', () => {
    const result: SyncResult = {
      refresh: { revision, created: false, warning: null },
      published: null,
      publish_error: null,
      unsent_comments: 0,
      marked_viewed: ['a.py'],
      not_viewed: { 'b.py': 'Not changed in the pull request' },
      viewed_error: null,
    }

    render(<SyncSummary result={result} />)

    expect(screen.getByText('No new commits. Marked 1 approved file as viewed on GitHub.')).toBeTruthy()
    expect(screen.getByRole('alert').textContent).toBe('not marked as viewed: b.py (Not changed in the pull request)')
  })
})
