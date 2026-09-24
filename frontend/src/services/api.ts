import { appConfig, apiUrl } from './config'

export class BackendUnavailableError extends Error {
  constructor(message = 'The AniRoute backend could not be reached.') {
    super(message)
    this.name = 'BackendUnavailableError'
  }
}

export async function postJson<T>(path: string, body: unknown): Promise<T> {
  let response: Response
  try {
    response = await fetch(apiUrl(path), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(12_000),
    })
  } catch {
    throw new BackendUnavailableError()
  }

  if (!response.ok) {
    let detail = `AniRoute backend returned ${response.status}.`
    try {
      const error = await response.json() as { detail?: string; message?: string }
      detail = error.detail || error.message || detail
    } catch {
      // Keep the short status message if the server did not return JSON.
    }
    throw new Error(detail)
  }
  return response.json() as Promise<T>
}

export async function checkBackend(): Promise<boolean> {
  try {
    const response = await fetch(apiUrl(appConfig.paths.health), { signal: AbortSignal.timeout(2_500) })
    return response.ok
  } catch {
    return false
  }
}
