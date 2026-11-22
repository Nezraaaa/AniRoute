import { appConfig, apiUrl } from './config'

const apiRequestTimeoutMs = 20_000

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
      signal: AbortSignal.timeout(apiRequestTimeoutMs),
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

async function readError(response: Response): Promise<Error> {
  let detail = `AniRoute backend returned ${response.status}.`
  try {
    const error = await response.json() as { detail?: string | Array<{ msg?: string }>; message?: string }
    if (typeof error.detail === 'string') detail = error.detail
    else if (Array.isArray(error.detail) && error.detail[0]?.msg) detail = error.detail[0].msg
    else if (error.message) detail = error.message
  } catch {
    // Keep the short status message if the server did not return JSON.
  }
  return new Error(detail)
}

export async function getJson<T>(path: string, timeoutMs = apiRequestTimeoutMs): Promise<T> {
  let response: Response
  try {
    response = await fetch(apiUrl(path), { headers: { Accept: 'application/json' }, signal: AbortSignal.timeout(timeoutMs) })
  } catch {
    throw new BackendUnavailableError()
  }
  if (!response.ok) throw await readError(response)
  return response.json() as Promise<T>
}

export async function postForm<T>(path: string, body: FormData, timeoutMs = 60_000): Promise<T> {
  let response: Response
  try {
    response = await fetch(apiUrl(path), { method: 'POST', body, headers: { Accept: 'application/json' }, signal: AbortSignal.timeout(timeoutMs) })
  } catch {
    throw new BackendUnavailableError()
  }
  if (!response.ok) throw await readError(response)
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
