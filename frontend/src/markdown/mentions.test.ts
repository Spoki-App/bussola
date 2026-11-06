import { describe, expect, it } from 'vitest'

import { filterMentions, mentionQuery } from './mentions'

describe('mentionQuery', () => {
  it.each([
    ['@', ''],
    ['Thanks @oct', 'oct'],
    ['(@mona-lisa', 'mona-lisa'],
    ['line\n@a', 'a'],
  ])('finds the mention being typed in %j', (text, query) => {
    expect(mentionQuery(text)).toBe(query)
  })

  it.each(['mail@example', 'Thanks @oct ', '`@code', 'no mention'])('ignores %j', (text) => {
    expect(mentionQuery(text)).toBeNull()
  })
})

describe('filterMentions', () => {
  const people = ['alice', 'bob', 'carol', 'malice', 'Alicia']

  it('lists prefix matches first, ignoring case', () => {
    expect(filterMentions(people, 'ali')).toEqual(['alice', 'Alicia', 'malice'])
  })

  it('lists everyone for an empty query, up to a limit', () => {
    expect(filterMentions(Array.from({ length: 20 }, (_, index) => `user${String(index)}`), '')).toHaveLength(8)
  })
})
