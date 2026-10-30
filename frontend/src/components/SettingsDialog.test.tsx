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

  it('opens a dialog with the pull request, repository, code font and line wrap sections', () => {
    render(
      <QueryClientProvider client={new QueryClient()}>
        <SettingsButton />
      </QueryClientProvider>,
    )

    fireEvent.click(screen.getByRole('button', { name: 'Settings' }))

    const dialog = screen.getByRole('dialog', { name: 'Settings' })
    expect(['Open pull request', 'Add repository', 'Code font', 'Line wrap'].map((name) => screen.getByRole('region', { name }).closest('dialog'))).toEqual([dialog, dialog, dialog, dialog])
    expect(screen.getByLabelText('GitHub link')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Close' }))
    expect(screen.queryByRole('dialog', { name: 'Settings' })).toBeNull()
  })
})
