import { describe, expect, it } from 'vitest'

import { imageUrl, isImagePath } from './images'

describe('images', () => {
  it('recognizes image files by extension', () => {
    expect(['release-assets/1-generated-codes.webp', 'logo.PNG', 'icon.svg', 'app.py', 'Makefile', 'archive.png.txt'].map(isImagePath)).toEqual([
      true,
      true,
      true,
      false,
      false,
      false,
    ])
  })

  it('builds the image address of each side', () => {
    expect(imageUrl(5, 12, 'base')).toBe('/api/reviews/5/units/12/image?side=base')
  })
})
