import { act, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import { setDiffLayout } from '../hooks/useDiffLayout'
import { DEFAULT_DIFF_LAYOUT } from '../settings/diffLayout'
import { DiffLayoutPanel, DiffLayoutSwitch } from './DiffLayoutPanel'

function stored(): unknown {
  return JSON.parse(window.localStorage.getItem('bussola.diffLayout') ?? 'null')
}

describe('DiffLayoutPanel', () => {
  afterEach(() => {
    act(() => {
      setDiffLayout(DEFAULT_DIFF_LAYOUT)
    })
    window.localStorage.clear()
  })

  it('starts on Automatic and keeps the review bar switch in step with Settings', () => {
    render(
      <>
        <section aria-label="Settings">
          <DiffLayoutPanel />
        </section>
        <section aria-label="Review bar">
          <DiffLayoutSwitch />
        </section>
      </>,
    )
    const settings = within(screen.getByRole('region', { name: 'Settings' }))
    const bar = within(screen.getByRole('region', { name: 'Review bar' }))
    expect(settings.getByRole('tab', { name: 'Automatic' })).toHaveAttribute('aria-selected', 'true')

    fireEvent.click(bar.getByRole('tab', { name: 'Split' }))

    expect(settings.getByRole('tab', { name: 'Split' })).toHaveAttribute('aria-selected', 'true')
    expect(stored()).toEqual({ layout: 'split', threshold: 1400 })

    fireEvent.click(settings.getByRole('tab', { name: 'Unified' }))

    expect(bar.getByRole('tab', { name: 'Unified' })).toHaveAttribute('aria-selected', 'true')
    expect(stored()).toEqual({ layout: 'unified', threshold: 1400 })
  })

  it('saves the Automatic threshold only once it is valid', () => {
    render(<DiffLayoutPanel />)
    const threshold = screen.getByLabelText('Automatic split from window width (px)')

    fireEvent.change(threshold, { target: { value: '12' } })
    expect(stored()).toBeNull()

    fireEvent.change(threshold, { target: { value: '1800' } })
    expect(stored()).toEqual({ layout: 'auto', threshold: 1800 })

    fireEvent.change(threshold, { target: { value: '' } })
    fireEvent.blur(threshold)
    expect(threshold).toHaveValue(1800)
  })
})
