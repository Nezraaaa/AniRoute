import { apiUrl, appConfig } from './config'
import type { AppMode, LocationSuggestion } from '@/types/aniRoute'

interface GeocodingResponseItem {
  place_id?: number | string
  osm_id?: number | string
  display_name?: string
  lat?: string | number
  lon?: string | number
  category?: string
  type?: string
}

export async function searchLocations(query: string, signal?: AbortSignal, mode: AppMode = 'live'): Promise<LocationSuggestion[]> {
  const trimmedQuery = query.trim()
  if (trimmedQuery.length < 2) return []
  if (mode === 'demo') return []

  const params = new URLSearchParams({ q: trimmedQuery, limit: '6' })
  let response: Response
  try {
    response = await fetch(`${apiUrl(appConfig.paths.geocode)}?${params.toString()}`, {
      headers: { Accept: 'application/json' },
      signal,
    })
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error
    throw new Error('Live location search backend is unavailable. Start the backend or switch to Demo mode.')
  }

  if (!response.ok) throw new Error(`Location search failed with status ${response.status}.`)

  const results = await response.json() as GeocodingResponseItem[]
  return results.flatMap((item, index) => {
    const latitude = Number(item.lat)
    const longitude = Number(item.lon)
    const displayName = item.display_name?.trim()
    if (!displayName || !Number.isFinite(latitude) || !Number.isFinite(longitude)) return []
    return [{
      id: String(item.place_id ?? item.osm_id ?? `location-${index}`),
      displayName,
      latitude,
      longitude,
      category: item.category ?? '',
      type: item.type ?? '',
      source: 'api' as const,
    }]
  })
}
