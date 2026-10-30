import { useMe } from './api/hooks'
import { OpenPullRequestRoute } from './OpenPullRequestRoute'
import { ReviewRoute } from './ReviewRoute'
import { SettingsButton } from './components/SettingsDialog'
import { HomePage } from './pages/HomePage'
import { Link } from './Link'
import { reviewIdFromPath, usePathname } from './navigation'
import { pullRequestUrlFromPath } from './review/pullRequestLink'

export default function App() {
  const pathname = usePathname()
  const me = useMe()
  const reviewId = reviewIdFromPath(pathname)
  const pullRequestUrl = pullRequestUrlFromPath(pathname)

  return (
    <div className="app">
      <header className="topbar">
        <Link to="/" className="brand">
          <img src="/favicon.svg" alt="" width="22" height="22" />
          bussola
        </Link>
        <span className="spacer" />
        {me.data && <span className="who" title={me.data.email}>{me.data.name}</span>}
        <SettingsButton />
      </header>
      {reviewId !== null ? (
        <ReviewRoute key={reviewId} reviewId={reviewId} />
      ) : pullRequestUrl ? (
        <OpenPullRequestRoute key={pullRequestUrl} url={pullRequestUrl} />
      ) : (
        <HomePage />
      )}
    </div>
  )
}
