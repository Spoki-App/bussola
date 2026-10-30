import { act, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import { setDiffWrap, syncDiffWrap } from '../settings/diffWrap'
import { DiffWrapButton, DiffWrapCheckbox } from './DiffWrapToggle'

describe('line wrap toggles', () => {
  afterEach(() => {
    setDiffWrap(true)
    window.localStorage.clear()
  })

  it('keeps the Settings checkbox and the review bar button in sync and remembers the choice', () => {
    render(
      <>
        <DiffWrapCheckbox />
        <DiffWrapButton />
      </>,
    )
    const checkbox = screen.getByRole('checkbox', { name: 'Wrap long lines' })
    const button = screen.getByRole('button', { name: 'Wrap lines' })
    expect(checkbox).toBeChecked()
    expect(button).toHaveAttribute('aria-pressed', 'true')

    fireEvent.click(button)
    expect(checkbox).not.toBeChecked()
    expect(button).toHaveAttribute('aria-pressed', 'false')
    expect(window.localStorage.getItem('bussola.diffWrap')).toBe('false')
    expect(document.documentElement.dataset.diffWrap).toBe('off')

    fireEvent.click(checkbox)
    expect(button).toHaveAttribute('aria-pressed', 'true')
    expect(window.localStorage.getItem('bussola.diffWrap')).toBe('true')
    expect(document.documentElement.dataset.diffWrap).toBe('on')
  })

  it('follows a change made in another tab', () => {
    syncDiffWrap()
    render(<DiffWrapButton />)

    window.localStorage.setItem('bussola.diffWrap', 'false')
    act(() => { window.dispatchEvent(new StorageEvent('storage', { key: 'bussola.diffWrap', newValue: 'false' })) })

    expect(screen.getByRole('button', { name: 'Wrap lines' })).toHaveAttribute('aria-pressed', 'false')
    expect(document.documentElement.dataset.diffWrap).toBe('off')
  })
})
