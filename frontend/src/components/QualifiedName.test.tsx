import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { QualifiedName } from './QualifiedName'

function parts(container: HTMLElement): [string | null | undefined, string | null | undefined, string | null | undefined] {
  return [
    container.querySelector('.unit-module')?.textContent,
    container.querySelector('.unit-parent')?.textContent,
    container.querySelector('.unit-name')?.textContent,
  ]
}

describe('QualifiedName', () => {
  it('shows a method with its module muted and its own name emphasized', () => {
    const { container } = render(<QualifiedName module="shop.billing.invoices" name="InvoiceService.create" />)

    expect(parts(container)).toEqual(['shop.billing.invoices.', 'InvoiceService.', 'create'])
    expect(container.querySelector('.unit-module')).toHaveClass('muted')
    expect(container.querySelector('.qualified-name')?.lastElementChild).toBe(screen.getByText('create'))
  })

  it('shows the full untruncated name as tooltip', () => {
    const { container } = render(<QualifiedName module="shop.billing.invoices" name="InvoiceService.Line.total" />)

    expect(container.querySelector('.qualified-name')).toHaveAttribute('title', 'shop.billing.invoices.InvoiceService.Line.total')
    expect(parts(container)).toEqual(['shop.billing.invoices.', 'InvoiceService.Line.', 'total'])
  })

  it('keeps copied text free of the bidi marks used for start truncation', () => {
    const { container } = render(<QualifiedName module="bussola.review.anchoring" name="Revision.refresh" />)

    expect(container.textContent).toBe('bussola.review.anchoring.Revision.refresh')
  })

  it('shows a top-level function after its module', () => {
    const { container } = render(<QualifiedName module="bussola.review.anchoring" name="find_line" />)

    expect(parts(container)).toEqual(['bussola.review.anchoring.', undefined, 'find_line'])
  })

  it('shows only the name without a module', () => {
    const { container } = render(<QualifiedName module={null} name="find_line" />)

    expect(container.querySelector('.unit-module')).toBeNull()
    expect(container.querySelector('.qualified-name')).toHaveAttribute('title', 'find_line')
  })
})
