import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen } from '@testing-library/react'
import { beforeAll, describe, expect, it } from 'vitest'

import { AppMenu } from './AppMenu'

describe('AppMenu', () => {
  beforeAll(() => {
    HTMLDialogElement.prototype.showModal = function showModal(this: HTMLDialogElement) {
      this.open = true
    }
    HTMLDialogElement.prototype.close = function close(this: HTMLDialogElement) {
      this.open = false
      this.dispatchEvent(new Event('close'))
    }
  })

  it('opens a dialog with the pull request, repository and code font sections', () => {
    render(
      <QueryClientProvider client={new QueryClient()}>
        <AppMenu />
      </QueryClientProvider>,
    )

    fireEvent.click(screen.getByRole('button', { name: 'Menu' }))

    const dialog = screen.getByRole('dialog', { name: 'Menu' })
    expect(['Open pull request', 'Add repository', 'Code font'].map((name) => screen.getByRole('region', { name }).closest('dialog'))).toEqual([dialog, dialog, dialog])
    expect(screen.getByLabelText('GitHub link')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Close' }))
    expect(screen.queryByRole('dialog', { name: 'Menu' })).toBeNull()
  })
})
