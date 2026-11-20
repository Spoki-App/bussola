import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { Icon, IconButton } from './IconButton'

describe('IconButton', () => {
  it('shows only its icon, named by its label in the accessible name and the tooltip', () => {
    const onClick = vi.fn()
    render(<IconButton label="Approve" icon={<Icon><path d="M3 8.5l3.2 3L13 4.5" /></Icon>} className="approve" onClick={onClick} />)

    const button = screen.getByRole('button', { name: 'Approve' })
    expect(button).toHaveAttribute('title', 'Approve')
    expect(button).toHaveTextContent('')
    expect(button).toHaveClass('icon-button', 'approve')
    expect(button.querySelector('svg.action-icon')).toHaveAttribute('aria-hidden', 'true')
    fireEvent.click(button)
    expect(onClick).toHaveBeenCalledOnce()
  })

  it('starts the tooltip with its label when it has a description', () => {
    render(<IconButton label="Describe" description="Ask the AI provider" icon={<Icon><path d="M0 0" /></Icon>} />)

    expect(screen.getByRole('button', { name: 'Describe' })).toHaveAttribute('title', 'Describe: Ask the AI provider')
  })
})
