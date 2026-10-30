import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import { CodeFontPanel } from './CodeFontPanel'

function open() {
  render(<CodeFontPanel />)
}

describe('CodeFontPanel', () => {
  afterEach(() => {
    window.localStorage.clear()
    document.documentElement.removeAttribute('style')
  })

  it('applies a font as soon as it is typed', () => {
    open()

    fireEvent.change(screen.getByLabelText('Font'), { target: { value: 'JetBrains Mono' } })

    expect(document.documentElement.style.getPropertyValue('--mono')).toMatch(/^"JetBrains Mono"/)
    expect(JSON.parse(window.localStorage.getItem('bussola.codeFont') ?? '{}')).toEqual({ family: 'JetBrains Mono', size: 12, ligatures: true, features: '' })
  })

  it('applies a size only once it is valid', () => {
    open()
    const size = screen.getByLabelText('Size')

    fireEvent.change(size, { target: { value: '1' } })
    expect(document.documentElement.style.getPropertyValue('--code-size')).toBe('')
    fireEvent.change(size, { target: { value: '15' } })
    expect(document.documentElement.style.getPropertyValue('--code-size')).toBe('15px')
  })
})
