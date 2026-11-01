import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen } from '@testing-library/react'
import { beforeAll, describe, expect, it } from 'vitest'

import { SettingsButton } from './SettingsDialog'

describe('SettingsButton', () => {
  beforeAll(() => {
    HTMLDialogElement.prototype.showModal = function showModal(this: HTMLDialogElement) {
      this.open = true
    }
    HTMLDialogElement.prototype.close = function close(this: HTMLDialogElement) {
      this.open = false
      this.dispatchEvent(new Event('close'))
    }
  })

  it('opens a dialog with the pull request, repository, code font, diff layout, line wrap and AI sections', () => {
    render(
      <QueryClientProvider client={new QueryClient()}>
        <SettingsButton />
      </QueryClientProvider>,
    )

    fireEvent.click(screen.getByRole('button', { name: 'Settings' }))

    const dialog = screen.getByRole('dialog', { name: 'Settings' })
    const sections = ['Open pull request', 'Add repository', 'Code font', 'Diff layout', 'Line wrap', 'AI']
    expect(sections.map((name) => screen.getByRole('region', { name }).closest('dialog'))).toEqual(sections.map(() => dialog))
    expect(screen.getByLabelText('GitHub link')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Close' }))
    expect(screen.queryByRole('dialog', { name: 'Settings' })).toBeNull()
  })
})
