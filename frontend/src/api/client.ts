const API_BASE = '/api'

export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    method,
    credentials: 'same-origin',
    headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  if (!response.ok) {
    throw new ApiError(response.status, await errorMessage(response))
  }
  return (await response.json()) as T
}

async function errorMessage(response: Response): Promise<string> {
  try {
    const payload = (await response.json()) as { detail?: unknown }
    if (typeof payload.detail === 'string') {
      return payload.detail
    }
    if (Array.isArray(payload.detail)) {
      return payload.detail.map((item: { msg?: string }) => item.msg ?? '').join('; ')
    }
  } catch {
    return `Request failed with status ${String(response.status)}`
  }
  return `Request failed with status ${String(response.status)}`
}

export const getJson = <T>(path: string) => request<T>('GET', path)
export const postJson = <T>(path: string, body?: unknown) => request<T>('POST', path, body ?? {})
export const patchJson = <T>(path: string, body: unknown) => request<T>('PATCH', path, body)
export const putJson = <T>(path: string, body: unknown) => request<T>('PUT', path, body)
export const deleteJson = <T>(path: string) => request<T>('DELETE', path)

export function describeError(error: unknown): string {
  if (error instanceof ApiError && error.status === 403) {
    return 'Not authorized. Open rtool with the link printed by `rtool serve`.'
  }
  return error instanceof Error ? error.message : 'Unexpected error'
}
