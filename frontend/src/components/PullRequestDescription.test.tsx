import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import type { ReviewPullRequest } from '../api/types'
import { PullRequestDescription } from './PullRequestDescription'

function pull(description: string | null): ReviewPullRequest {
  return { number: 7, title: 'Sum the items', url: 'https://github.com/acme/widgets/pull/7', author: 'bob', state: 'OPEN', description }
}

describe('PullRequestDescription', () => {
  it('renders the description as Markdown with its author', () => {
    render(<PullRequestDescription pull={pull('Fixes **totals**')} />)

    expect(screen.getByText('totals').tagName).toBe('STRONG')
    expect(screen.getByText('by bob')).toBeInTheDocument()
  })

  it('says when there is no description', () => {
    render(<PullRequestDescription pull={pull('  ')} />)

    expect(screen.getByText('No description provided.')).toBeInTheDocument()
  })

  it('clamps long descriptions until expanded', () => {
    render(<PullRequestDescription pull={pull(Array.from({ length: 30 }, (_, line) => `line ${String(line)}`).join('\n\n'))} />)

    fireEvent.click(screen.getByRole('button', { name: 'Show all' }))

    expect(screen.getByRole('button', { name: 'Show less' })).toBeInTheDocument()
  })
})
