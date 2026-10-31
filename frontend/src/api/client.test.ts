import { afterEach, describe, expect, it, vi } from 'vitest'

import { ApiError, postJson } from './client'

function respond(status: number, body: unknown) {
  vi.stubGlobal('fetch', vi.fn(() => Promise.resolve(Response.json(body, { status }))))
}

async function failure(): Promise<ApiError> {
  try {
    await postJson('/pulls/open', { url: 'https://github.com/acme/widgets/pull/7' })
  } catch (error) {
    if (error instanceof ApiError) {
      return error
    }
  }
  throw new Error('Expected an ApiError')
}

describe('ApiError', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('carries the error code the server sends', async () => {
    respond(404, { detail: 'No local clone of github.com/acme/widgets was found.', code: 'no_local_clone' })

    const error = await failure()

    expect([error.status, error.code, error.message]).toEqual([404, 'no_local_clone', 'No local clone of github.com/acme/widgets was found.'])
  })

  it('has no code for other errors', async () => {
    respond(404, { detail: 'Not Found' })

    expect((await failure()).code).toBeNull()
  })
})
