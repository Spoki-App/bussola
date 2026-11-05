import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, within } from '@testing-library/react'
import { beforeAll, describe, expect, it } from 'vitest'

import { setDiffWrap } from '../settings/diffWrap'
import { SettingsButton } from './SettingsDialog'

function openSettings() {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <SettingsButton />
    </QueryClientProvider>,
  )
  fireEvent.click(screen.getByRole('button', { name: 'Settings' }))
  return screen.getByRole('dialog', { name: 'Settings' })
}

function categoryButtons() {
  return within(screen.getByRole('navigation', { name: 'Setting categories' })).queryAllByRole('button')
}

function shownSettings() {
  return within(screen.getByRole('dialog')).queryAllByRole('region').filter((region) => region.classList.contains('setting')).map((region) => region.querySelector('h4')?.textContent)
}

describe('SettingsButton', () => {
  beforeAll(() => {
    HTMLDialogElement.prototype.showModal = function showModal(this: HTMLDialogElement) {
      this.open = true
    }
    HTMLDialogElement.prototype.close = function close(this: HTMLDialogElement) {
      this.open = false
      this.dispatchEvent(new Event('close'))
    }
    Element.prototype.scrollIntoView = () => undefined
  })

  it('lists the categories on the left, focuses the search and shows the first category', () => {
    openSettings()

    expect(categoryButtons().map((button) => button.textContent)).toEqual(['Pull requests', 'Repositories', 'Appearance', 'Diff', 'AI'])
    expect(screen.getByRole('button', { name: 'Pull requests' })).toHaveAttribute('aria-current', 'true')
    expect(screen.getByRole('searchbox', { name: 'Search settings' })).toHaveFocus()
    expect(shownSettings()).toEqual(['Open pull request'])
    expect(screen.getByLabelText('GitHub link')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Close' }))
    expect(screen.queryByRole('dialog', { name: 'Settings' })).toBeNull()
  })

  it('shows the settings of the selected category', () => {
    openSettings()

    fireEvent.click(screen.getByRole('button', { name: 'Diff' }))
    expect(screen.getByRole('button', { name: 'Diff' })).toHaveAttribute('aria-current', 'true')
    expect(shownSettings()).toEqual(['Diff layout', 'Line wrap'])

    fireEvent.click(screen.getByRole('button', { name: 'AI' }))
    expect(shownSettings()).toEqual(['AI provider', 'AI prompts'])
  })

  it('moves between categories with the arrow keys, Home and End', () => {
    openSettings()
    const [first] = categoryButtons()
    first.focus()

    fireEvent.keyDown(first, { key: 'ArrowDown' })
    expect(screen.getByRole('button', { name: 'Repositories' })).toHaveFocus()
    expect(shownSettings()).toEqual(['Add repository'])

    fireEvent.keyDown(document.activeElement ?? first, { key: 'End' })
    expect(screen.getByRole('button', { name: 'AI' })).toHaveFocus()
    expect(shownSettings()).toEqual(['AI provider', 'AI prompts'])

    fireEvent.keyDown(document.activeElement ?? first, { key: 'ArrowDown' })
    expect(screen.getByRole('button', { name: 'AI' })).toHaveFocus()

    fireEvent.keyDown(document.activeElement ?? first, { key: 'ArrowUp' })
    expect(screen.getByRole('button', { name: 'Diff' })).toHaveFocus()
    expect(shownSettings()).toEqual(['Diff layout', 'Line wrap'])

    fireEvent.keyDown(document.activeElement ?? first, { key: 'Home' })
    expect(screen.getByRole('button', { name: 'Pull requests' })).toHaveFocus()
  })

  it('searches names and descriptions across categories and highlights the matches', () => {
    const dialog = openSettings()

    fireEvent.change(screen.getByRole('searchbox', { name: 'Search settings' }), { target: { value: 'WRAP' } })
    expect(shownSettings()).toEqual(['Line wrap'])
    expect(categoryButtons().map((button) => button.textContent)).toEqual(['Diff'])
    expect(Array.from(dialog.querySelectorAll('mark'), (mark) => mark.textContent)).toEqual(['wrap', 'Wrap'])

    fireEvent.change(screen.getByRole('searchbox', { name: 'Search settings' }), { target: { value: 'model' } })
    expect(shownSettings()).toEqual(['AI provider', 'AI prompts'])

    fireEvent.change(screen.getByRole('searchbox', { name: 'Search settings' }), { target: { value: 'font' } })
    expect(shownSettings()).toEqual(['Code font'])
    expect(categoryButtons().map((button) => button.textContent)).toEqual(['Appearance'])
  })

  it('says so when no setting matches the search', () => {
    openSettings()

    fireEvent.change(screen.getByRole('searchbox', { name: 'Search settings' }), { target: { value: 'nothing like this' } })
    expect(shownSettings()).toEqual([])
    expect(categoryButtons()).toEqual([])
    expect(screen.getByText('No settings match "nothing like this".')).toBeInTheDocument()

    fireEvent.change(screen.getByRole('searchbox', { name: 'Search settings' }), { target: { value: '' } })
    expect(shownSettings()).toEqual(['Open pull request'])
  })

  it('keeps the stored value of a setting and saves changes to it', () => {
    setDiffWrap(false)
    openSettings()
    fireEvent.click(screen.getByRole('button', { name: 'Diff' }))

    const wrap = screen.getByRole('checkbox', { name: 'Wrap long lines' })
    expect(wrap).not.toBeChecked()
    fireEvent.click(wrap)
    expect(wrap).toBeChecked()
    expect(window.localStorage.getItem('bussola.diffWrap')).toBe('true')
  })
})
