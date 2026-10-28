const IMAGE_EXTENSIONS = new Set(['png', 'jpg', 'jpeg', 'gif', 'webp', 'avif', 'bmp', 'ico', 'svg'])

export function isImagePath(path: string): boolean {
  const name = path.split('/').at(-1) ?? ''
  return name.includes('.') && IMAGE_EXTENSIONS.has(name.split('.').at(-1)?.toLowerCase() ?? '')
}

export function imageUrl(reviewId: number, unitId: number, side: 'base' | 'head'): string {
  return `/api/reviews/${String(reviewId)}/units/${String(unitId)}/image?side=${side}`
}
