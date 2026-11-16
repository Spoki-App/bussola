import assert from 'node:assert/strict'
import { test } from 'node:test'

import { bussolaLink, githubPage } from './link.js'

const at = (address) => new URL(address, 'https://bussola.spoki.com')

test('a GitHub pull request path becomes a bussola link, keeping the query and the anchor', () => {
  assert.equal(bussolaLink(at('/github.com/Spoki-App/spoki-wallet/pull/10')), 'bussola://github.com/Spoki-App/spoki-wallet/pull/10')
  assert.equal(bussolaLink(at('/github.com/acme/shop/pull/482/files?w=1#discussion_r123')), 'bussola://github.com/acme/shop/pull/482/files?w=1#discussion_r123')
})

test('a review path becomes a bussola review link', () => {
  assert.equal(bussolaLink(at('/review?repo=acme/shop&pr=482&path=src/app.py&line=42')), 'bussola://review?repo=acme/shop&pr=482&path=src/app.py&line=42')
})

test('extra leading slashes are dropped', () => {
  assert.equal(bussolaLink(at('https://bussola.spoki.com//github.com/acme/shop/pull/1')), 'bussola://github.com/acme/shop/pull/1')
})

test('the root has no bussola link', () => {
  assert.equal(bussolaLink(at('/')), null)
  assert.equal(bussolaLink(at('/?x=1#y')), null)
})

test('the GitHub page of a GitHub path is the original link', () => {
  assert.equal(githubPage(at('/github.com/acme/shop/pull/482/files#r9')), 'https://github.com/acme/shop/pull/482/files#r9')
})

test('the GitHub page of a review link is its pull request', () => {
  assert.equal(githubPage(at('/review?repo=acme/shop&pr=482&line=4')), 'https://github.com/acme/shop/pull/482')
})

test('there is no GitHub page for other hosts or invalid review links', () => {
  for (const address of [
    '/',
    '/gitlab.com/acme/shop/pull/1',
    '/github.com.evil.example/acme',
    '/github.com@evil.example/acme',
    '/evil.example/github.com/acme',
    '/review?repo=acme&pr=1',
    '/review?repo=acme/shop&pr=0',
    '/review?repo=acme/shop&pr=abc',
    '/review?repo=acme/shop/x&pr=1',
  ]) {
    assert.equal(githubPage(at(address)), null, address)
  }
})
