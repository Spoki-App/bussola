import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import type { Unit } from '../api/types'
import { buildUnitTree } from '../review/unitTree'
import { QualifiedName } from './QualifiedName'
import { UnitTree } from './UnitTree'

function method(id: number, qualifiedName: string): Unit {
  return {
    id,
    revision_id: 1,
    path: 'src/shop/billing/invoices.py',
    old_path: null,
    module: 'shop.billing.invoices',
    kind: 'method',
    qualified_name: qualifiedName,
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
  }
}

describe('UnitTree', () => {
  it('names the class stand-in and its methods with the module', () => {
    const units = [method(1, 'InvoiceService.create'), method(2, 'InvoiceService.cancel')]
    const { container } = render(
      <UnitTree
        nodes={buildUnitTree(units)}
        module="shop.billing.invoices"
        renderUnit={(unit) => <QualifiedName key={unit.id} module={unit.module} name={unit.qualified_name} />}
      />,
    )

    const titles = [...container.querySelectorAll('.qualified-name')].map((title) => title.getAttribute('title'))
    expect(titles).toEqual(['shop.billing.invoices.InvoiceService', 'shop.billing.invoices.InvoiceService.create', 'shop.billing.invoices.InvoiceService.cancel'])
    expect(screen.getByText('create')).toHaveClass('unit-name')
  })
})
