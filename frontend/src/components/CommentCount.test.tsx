import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { CommentCount } from './CommentCount'

describe('CommentCount', () => {
  it('shows the total and the unresolved threads', () => {
    render(<CommentCount total={6} unresolved={1} totalLabel="comment" />)

    expect(screen.getByLabelText('6 comments, 1 unresolved')).toBeInTheDocument()
    expect(screen.getByText('1 unresolved')).toBeInTheDocument()
  })

  it('shows only the total when everything is resolved', () => {
    render(<CommentCount total={1} unresolved={0} totalLabel="thread" />)

    expect(screen.getByLabelText('1 thread')).toBeInTheDocument()
    expect(screen.queryByText(/unresolved/)).toBeNull()
  })

  it('renders an empty placeholder without comments', () => {
    const { container } = render(<CommentCount total={0} unresolved={0} totalLabel="comment" />)

    expect(container.textContent).toBe('')
  })
})
