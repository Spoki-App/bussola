import assert from 'node:assert/strict'
import { test } from 'node:test'

import { handOff } from './handoff.js'

function fakeWindow({ canClose }) {
  const document = Object.assign(new EventTarget(), { visibilityState: 'visible' })
  const window = Object.assign(new EventTarget(), {
    document,
    closed: false,
    closeCalls: 0,
    setTimeout,
    clearTimeout,
    close() {
      this.closeCalls += 1
      this.closed = canClose
    },
    hide() {
      document.visibilityState = 'hidden'
      document.dispatchEvent(new Event('visibilitychange'))
    },
  })
  return window
}

test('the tab closes when it loses focus after the handoff', async () => {
  const window = fakeWindow({ canClose: true })
  const outcome = handOff(window, 1000)
  window.dispatchEvent(new Event('blur'))
  assert.equal(await outcome, 'closed')
  assert.equal(window.closeCalls, 1)
})

test('the tab closes when it becomes hidden after the handoff', async () => {
  const window = fakeWindow({ canClose: true })
  const outcome = handOff(window, 1000)
  window.hide()
  assert.equal(await outcome, 'closed')
})

test('a visibility change that keeps the tab visible is not a handoff', async () => {
  const window = fakeWindow({ canClose: true })
  const outcome = handOff(window, 20)
  window.document.dispatchEvent(new Event('visibilitychange'))
  assert.equal(await outcome, 'unconfirmed')
  assert.equal(window.closeCalls, 0)
})

test('the tab stays open when the browser refuses to close it', async () => {
  const window = fakeWindow({ canClose: false })
  const outcome = handOff(window, 1000)
  window.dispatchEvent(new Event('blur'))
  assert.equal(await outcome, 'open')
  assert.equal(window.closeCalls, 1)
})

test('without losing focus in time the handoff is unconfirmed and later focus changes are ignored', async () => {
  const window = fakeWindow({ canClose: true })
  assert.equal(await handOff(window, 20), 'unconfirmed')
  window.dispatchEvent(new Event('blur'))
  window.hide()
  assert.equal(window.closeCalls, 0)
})
