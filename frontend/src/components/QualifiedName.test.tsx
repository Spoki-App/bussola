import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { QualifiedName } from './QualifiedName'

describe('QualifiedName', () => {
  it('shows the module muted before the name, with the full value as tooltip', () => {
    const { container } = render(<QualifiedName module="bussola.review.anchoring" name="find_line" />)

    const name = screen.getByText('find_line')
    const module = container.querySelector('.unit-module')
    expect(name).toHaveClass('unit-name')
    expect(module?.textContent).toBe('bussola.review.anchoring.')
    expect(module?.nextElementSibling).toBe(name)
    expect(container.querySelector('.qualified-name')).toHaveAttribute('title', 'bussola.review.anchoring.find_line')
  })

  it('keeps copied text free of the bidi marks used for left truncation', () => {
    const { container } = render(<QualifiedName module="bussola.review.anchoring" name="find_line" />)

    expect(container.textContent).toBe('bussola.review.anchoring.find_line')
  })

  it('shows only the name without a module', () => {
    const { container } = render(<QualifiedName module={null} name="find_line" />)

    expect(container.querySelector('.unit-module')).toBeNull()
    expect(container.querySelector('.qualified-name')).toHaveAttribute('title', 'find_line')
  })
})
