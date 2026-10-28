import { useMe } from './api/hooks'
import { OpenPullRequestRoute } from './OpenPullRequestRoute'
import { ReviewRoute } from './ReviewRoute'
import { HomePage } from './pages/HomePage'
import { Link } from './Link'
import { usePathname } from './navigation'
import { pullRequestUrlFromPath } from './review/pullRequestLink'

const REVIEW_PATH = /^\/reviews\/(\d+)\/?$/

export default function App() {
  const pathname = usePathname()
  const me = useMe()
  const reviewMatch = REVIEW_PATH.exec(pathname)
  const pullRequestUrl = pullRequestUrlFromPath(pathname)

  return (
    <div className="app">
      <header className="topbar">
        <Link to="/" className="brand">
          <img src="/favicon.svg" alt="" width="22" height="22" />
          rtool
        </Link>
        <span className="spacer" />
        {me.data && <span className="muted">{`${me.data.name} <${me.data.email}>`}</span>}
      </header>
      {reviewMatch ? (
        <ReviewRoute key={reviewMatch[1]} reviewId={Number(reviewMatch[1])} />
      ) : pullRequestUrl ? (
        <OpenPullRequestRoute key={pullRequestUrl} url={pullRequestUrl} />
      ) : (
        <HomePage />
      )}
    </div>
  )
}
