import { afterEach, describe, expect, it } from 'vitest'

import type { DiffRow } from '../api/types'
import { DEFAULT_DIFF_LAYOUT, hasModification, loadDiffLayout, resolveViewType, saveDiffLayout } from './diffLayout'

function row(change: DiffRow['change']): DiffRow {
  return { change, old_index: 0, new_index: 0, old_line: 1, new_line: 1, text: '', row_hash: null, approved: false, selection_id: null, placeholder: false }
}

const rewritten = [row('context'), row('removed'), row('added'), row('context')]
const inserted = [row('added'), row('added')]
const deleted = [row('removed'), row('removed')]
const apart = [row('removed'), row('context'), row('added')]

describe('hasModification', () => {
  it('needs removed and added lines in the same block of changes', () => {
    expect(hasModification(rewritten)).toBe(true)
    expect(hasModification([row('added'), row('removed')])).toBe(true)
    expect(hasModification(inserted)).toBe(false)
    expect(hasModification(deleted)).toBe(false)
    expect(hasModification(apart)).toBe(false)
    expect(hasModification([])).toBe(false)
  })
})

describe('resolveViewType', () => {
  it('splits a rewritten unit on a wide window', () => {
    expect(resolveViewType('auto', true, rewritten)).toBe('split')
  })

  it('keeps one column on a narrow window', () => {
    expect(resolveViewType('auto', false, rewritten)).toBe('unified')
  })

  it('keeps one column for a new or deleted unit even on a wide window', () => {
    expect(resolveViewType('auto', true, inserted)).toBe('unified')
    expect(resolveViewType('auto', true, deleted)).toBe('unified')
  })

  it('follows a fixed layout whatever the width and the change', () => {
    expect(resolveViewType('split', false, inserted)).toBe('split')
    expect(resolveViewType('unified', true, rewritten)).toBe('unified')
  })
})

describe('loadDiffLayout', () => {
  afterEach(() => {
    window.localStorage.clear()
  })

  it('defaults to automatic from 1400px', () => {
    expect(loadDiffLayout()).toEqual({ layout: 'auto', threshold: 1400 })
  })

  it('reads back what was saved', () => {
    saveDiffLayout({ layout: 'split', threshold: 1800 })
    expect(loadDiffLayout()).toEqual({ layout: 'split', threshold: 1800 })
  })

  it('ignores unknown layouts and clamps the threshold', () => {
    window.localStorage.setItem('bussola.diffLayout', JSON.stringify({ layout: 'sideways', threshold: 10 }))
    expect(loadDiffLayout()).toEqual({ layout: 'auto', threshold: 600 })
    window.localStorage.setItem('bussola.diffLayout', JSON.stringify({ layout: 'constructor', threshold: 1400 }))
    expect(loadDiffLayout()).toEqual(DEFAULT_DIFF_LAYOUT)
    window.localStorage.setItem('bussola.diffLayout', 'not json')
    expect(loadDiffLayout()).toEqual(DEFAULT_DIFF_LAYOUT)
  })
})
