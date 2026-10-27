import { ReviewPage } from './pages/ReviewPage'

export function ReviewRoute({ reviewId }: { reviewId: number }) {
  return <ReviewPage reviewId={reviewId} />
}
