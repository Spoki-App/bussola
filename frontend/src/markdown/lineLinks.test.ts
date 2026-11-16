import { describe, expect, it } from 'vitest'

import { lineLinksAsText } from './lineLinks'

describe('lineLinksAsText', () => {
  it('keeps the text of line links and leaves other links alone', () => {
    const markdown = 'See [the total](#after:app.py:3), [the old line](<#before:app.py:9>), [this](#after-4) and [docs](https://example.com/#after:x:1).'

    expect(lineLinksAsText(markdown)).toBe('See the total, the old line, this and [docs](https://example.com/#after:x:1).')
  })

  it('keeps anchors that are not line links', () => {
    expect(lineLinksAsText('[top](#after) and [encoded](#after%3Aapp.py%3A3)')).toBe('[top](#after) and encoded')
  })
})
