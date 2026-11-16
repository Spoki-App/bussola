const GITHUB_PREFIX = 'github.com/'
const REVIEW_PATH = 'review'
const REPOSITORY = /^[A-Za-z0-9_.-]{1,100}\/[A-Za-z0-9_.-]{1,100}$/
const PULL_NUMBER = /^[1-9][0-9]{0,8}$/

function linkPath(location) {
  return location.pathname.replace(/^\/+/, '')
}

export function bussolaLink(location) {
  const path = linkPath(location)
  return path ? `bussola://${path}${location.search}${location.hash}` : null
}

export function githubPage(location) {
  const path = linkPath(location)
  if (path.startsWith(GITHUB_PREFIX)) {
    return `https://${path}${location.search}${location.hash}`
  }
  if (path !== REVIEW_PATH) {
    return null
  }
  const params = new URLSearchParams(location.search)
  const repository = params.get('repo') ?? ''
  const number = params.get('pr') ?? ''
  return REPOSITORY.test(repository) && PULL_NUMBER.test(number) ? `https://github.com/${repository}/pull/${number}` : null
}
