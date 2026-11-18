import assert from 'node:assert/strict'
import { test } from 'node:test'

import { handOff } from './handoff.js'

function fakeWindow() {
  const document = Object.assign(new EventTarget(), { visibilityState: 'visible' })
  return Object.assign(new EventTarget(), {
    document,
    closeCalls: 0,
    setTimeout,
    close() {
      this.closeCalls += 1
    },
    hide() {
      document.visibilityState = 'hidden'
      document.dispatchEvent(new Event('visibilitychange'))
    },
  })
}

test('losing focus after the handoff closes the tab', async () => {
  const window = fakeWindow()
  const opened = handOff(window, 1000)
  window.dispatchEvent(new Event('blur'))
  assert.equal(await opened, true)
  assert.equal(window.closeCalls, 1)
})

test('becoming hidden after the handoff closes the tab', async () => {
  const window = fakeWindow()
  const opened = handOff(window, 1000)
  window.hide()
  assert.equal(await opened, true)
  assert.equal(window.closeCalls, 1)
})

test('a visibility change that keeps the tab visible is not a handoff', async () => {
  const window = fakeWindow()
  const opened = handOff(window, 20)
  window.document.dispatchEvent(new Event('visibilitychange'))
  assert.equal(await opened, false)
  assert.equal(window.closeCalls, 0)
})

test('focus lost after the delay leaves the tab open', async () => {
  const window = fakeWindow()
  assert.equal(await handOff(window, 20), false)
  window.dispatchEvent(new Event('blur'))
  window.hide()
  assert.equal(window.closeCalls, 0)
})
