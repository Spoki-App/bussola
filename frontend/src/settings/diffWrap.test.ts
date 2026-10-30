import { act, renderHook } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import { loadDiffWrap, setDiffWrap, useDiffWrap } from './diffWrap'

describe('diff wrap setting', () => {
  afterEach(() => {
    setDiffWrap(true)
    window.localStorage.clear()
  })

  it('is on by default', () => {
    window.localStorage.clear()
    expect(loadDiffWrap()).toBe(true)
  })

  it('remembers the choice in the browser', () => {
    setDiffWrap(false)
    expect(window.localStorage.getItem('bussola.diffWrap')).toBe('false')
    expect(loadDiffWrap()).toBe(false)
  })

  it('updates every component that reads it', () => {
    const first = renderHook(() => useDiffWrap())
    const second = renderHook(() => useDiffWrap())
    expect([first.result.current, second.result.current]).toEqual([true, true])

    act(() => { setDiffWrap(false) })

    expect([first.result.current, second.result.current]).toEqual([false, false])
  })
})
