const API_BASE = '/api'

export class ApiError extends Error {
  readonly status: number
  readonly code: string | null

  constructor(status: number, message: string, code: string | null = null) {
    super(message)
    this.status = status
    this.code = code
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
    throw await apiError(response)
  }
  return (await response.json()) as T
}

async function apiError(response: Response): Promise<ApiError> {
  const fallback = `Request failed with status ${String(response.status)}`
  try {
    const payload = (await response.json()) as { detail?: unknown; code?: unknown }
    const code = typeof payload.code === 'string' ? payload.code : null
    if (typeof payload.detail === 'string') {
      return new ApiError(response.status, payload.detail, code)
    }
    if (Array.isArray(payload.detail)) {
      return new ApiError(response.status, payload.detail.map((item: { msg?: string }) => item.msg ?? '').join('; '), code)
    }
  } catch {
    return new ApiError(response.status, fallback)
  }
  return new ApiError(response.status, fallback)
}

export const getJson = <T>(path: string) => request<T>('GET', path)
export const postJson = <T>(path: string, body?: unknown) => request<T>('POST', path, body ?? {})
export const patchJson = <T>(path: string, body: unknown) => request<T>('PATCH', path, body)
export const putJson = <T>(path: string, body: unknown) => request<T>('PUT', path, body)
export const deleteJson = <T>(path: string) => request<T>('DELETE', path)

export function describeError(error: unknown): string {
  if (error instanceof ApiError && error.status === 403) {
    return 'Not authorized. Open bussola with the link printed by `bussola serve`.'
  }
  return error instanceof Error ? error.message : 'Unexpected error'
}
