import { handOff } from './handoff.js'
import { bussolaLink, githubPage } from './link.js'

const FALLBACK_DELAY_MS = 1500

function show(id) {
  document.getElementById(id).hidden = false
}

function hide(id) {
  document.getElementById(id).hidden = true
}

function openLink(link) {
  hide('usage')
  document.getElementById('target').textContent = link
  document.getElementById('open').href = link
  const github = githubPage(window.location)
  if (github) {
    document.getElementById('github').href = github
    show('github-item')
  }
  show('opening')
  handOff(window, FALLBACK_DELAY_MS).then((opened) => {
    if (opened) {
      show('opened')
    } else {
      show('fallback')
    }
  })
  window.location.href = link
}

const link = bussolaLink(window.location)
if (link) {
  openLink(link)
}
