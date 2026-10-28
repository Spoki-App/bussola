export function imageUrl(reviewId: number, unitId: number, side: 'base' | 'head'): string {
  return `/api/reviews/${String(reviewId)}/units/${String(unitId)}/image?side=${side}`
}
