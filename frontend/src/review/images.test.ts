import { describe, expect, it } from 'vitest'

import { imageUrl } from './images'

describe('images', () => {
  it('builds the image address of each side', () => {
    expect(imageUrl(5, 12, 'base')).toBe('/api/reviews/5/units/12/image?side=base')
  })
})
