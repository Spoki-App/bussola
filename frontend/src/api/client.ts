const API_BASE = '/api'

export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

export async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, { credentials: 'same-origin' })
  if (!response.ok) {
    throw new ApiError(response.status, `GET ${path} failed with ${String(response.status)}`)
  }
  return (await response.json()) as T
}
