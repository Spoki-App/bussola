import { bussolaLink, githubPage } from './link.js'

const FALLBACK_DELAY_MS = 1500

function show(id) {
  document.getElementById(id).hidden = false
}

function openLink(link) {
  document.getElementById('usage').hidden = true
  document.getElementById('target').textContent = link
  document.getElementById('open').href = link
  const github = githubPage(window.location)
  if (github) {
    document.getElementById('github').href = github
    show('github-item')
  }
  show('opening')
  window.setTimeout(() => show('fallback'), FALLBACK_DELAY_MS)
  window.location.href = link
}

const link = bussolaLink(window.location)
if (link) {
  openLink(link)
}
