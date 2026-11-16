import { act, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import { setUnitWidth } from '../settings/unitWidth'
import { UnitWidthButton, UnitWidthPanel } from './UnitWidthPanel'

describe('unit width controls', () => {
  afterEach(() => {
    setUnitWidth('auto')
    window.localStorage.clear()
  })

  it('shows the repository line length and its source on the review bar button', () => {
    render(<UnitWidthButton lineLength={{ columns: 99, source: '.editorconfig' }} />)

    const button = screen.getByRole('button', { name: 'Width Auto 99' })
    expect(button).toHaveAttribute('title', 'Unit width: Auto, 99, from .editorconfig. Click for the next width.')
  })

  it('keeps Settings and the review bar in sync and remembers the choice', () => {
    render(
      <>
        <UnitWidthPanel />
        <UnitWidthButton lineLength={undefined} />
      </>,
    )
    expect(screen.getByRole('tab', { name: 'Auto' })).toHaveAttribute('aria-selected', 'true')

    fireEvent.click(screen.getByRole('button', { name: 'Width Auto 120' }))
    expect(screen.getByRole('tab', { name: '80' })).toHaveAttribute('aria-selected', 'true')
    expect(window.localStorage.getItem('bussola.unitWidth')).toBe('80ch')

    fireEvent.click(screen.getByRole('tab', { name: 'Full' }))
    expect(screen.getByRole('button', { name: 'Width Full' })).toHaveAttribute('title', 'Unit width: Full, all the available space. Click for the next width.')
    expect(window.localStorage.getItem('bussola.unitWidth')).toBe('full')
  })

  it('follows a change made in another tab', () => {
    render(<UnitWidthButton lineLength={undefined} />)

    window.localStorage.setItem('bussola.unitWidth', '160ch')
    act(() => { window.dispatchEvent(new StorageEvent('storage', { key: 'bussola.unitWidth', newValue: '160ch' })) })

    expect(screen.getByRole('button', { name: 'Width 160' })).toBeInTheDocument()
  })
})
