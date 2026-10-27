import { useMe } from './api/hooks'
import { ReviewRoute } from './ReviewRoute'
import { HomePage } from './pages/HomePage'
import { Link } from './Link'
import { usePathname } from './navigation'

const REVIEW_PATH = /^\/reviews\/(\d+)\/?$/

export default function App() {
  const pathname = usePathname()
  const me = useMe()
  const reviewMatch = REVIEW_PATH.exec(pathname)

  return (
    <div className="app">
      <header className="topbar">
        <Link to="/" className="brand">
          rtool
        </Link>
        <span className="spacer" />
        {me.data && <span className="muted">{`${me.data.name} <${me.data.email}>`}</span>}
      </header>
      {reviewMatch ? <ReviewRoute key={reviewMatch[1]} reviewId={Number(reviewMatch[1])} /> : <HomePage />}
    </div>
  )
}
