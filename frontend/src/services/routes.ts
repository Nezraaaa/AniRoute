import { makePresentationRoutes } from '@/data/presentation'
import type { AppMode, DataSource, HazardType, RouteOption, RouteResult, TripInput } from '@/types/aniRoute'
import { appConfig } from './config'
import { BackendUnavailableError, postJson } from './api'

interface ApiRoute {
  route_id: string
  category: RouteOption['category']
  categories?: RouteOption['categories']
  geometry: RouteOption['geometry']
  travel_time_minutes: number
  distance_km: number
  road_condition_summary: string
  weather_flood_summary: string
  temperature_exposure_summary: string
  crop_risk_score: number | null
  crop_risk_label: RouteOption['cropRiskLabel']
  explanation: string
  recommended: boolean
  known_hazards: Array<{
    id: string
    name: string
    coordinates: { latitude: number; longitude: number }
    note: string
  }>
  risk_factors?: RouteOption['riskFactors']
  crop_profile_summary?: string
}

interface ApiRouteResponse {
  routes: ApiRoute[]
  data_source?: DataSource
  message?: string
  recommended_route_id?: string
}

interface RecalculateResponse extends ApiRouteResponse {
  changed?: boolean
}

function mapApiRoute(route: ApiRoute, source: DataSource): RouteOption {
  return {
    id: route.route_id,
    category: route.category,
    categories: route.categories,
    geometry: route.geometry,
    travelTimeMinutes: route.travel_time_minutes,
    distanceKm: route.distance_km,
    roadConditionSummary: route.road_condition_summary,
    weatherFloodSummary: route.weather_flood_summary,
    temperatureSummary: route.temperature_exposure_summary,
    cropRiskScore: route.crop_risk_score,
    cropRiskLabel: route.crop_risk_label,
    riskFactors: route.risk_factors ?? { travelTime: 0, distance: 0, road: 0, floodWeather: 0, temperature: 0 },
    cropProfileSummary: route.crop_profile_summary ?? 'Crop sensitivity is included in the route score.',
    explanation: route.explanation,
    recommended: route.recommended,
    knownHazards: route.known_hazards ?? [],
    source,
  }
}

function unwrapRouteResponse(data: ApiRouteResponse, fallbackSource: DataSource): RouteResult {
  const source = data.data_source ?? fallbackSource
  const routes = (data.routes ?? []).map(route => mapApiRoute(route, source))
  return {
    routes,
    source,
    message: data.message,
    recommendedRouteId: data.recommended_route_id ?? routes.find(route => route.recommended)?.id ?? routes[0]?.id ?? 'optimal',
  }
}

function assertLiveRouteData(data: ApiRouteResponse) {
  if (data.data_source && data.data_source !== 'api') {
    throw new Error('The connected route engine did not return production route data.')
  }
}

export async function calculateRoutes(trip: TripInput, mode: AppMode = 'live'): Promise<RouteResult> {
  if (mode === 'presentation') {
    const routes = makePresentationRoutes(trip)
    return {
      routes, source: 'presentation',
      message: 'Crop-aware route options calculated for this presentation scenario.',
      recommendedRouteId: routes.find(route => route.recommended)?.id ?? 'optimal',
    }
  }

  try {
    const response = await postJson<ApiRouteResponse>(appConfig.paths.routes, trip)
    assertLiveRouteData(response)
    const result = unwrapRouteResponse(response, 'api')
    if (result.routes.length > 0) return result
    throw new Error('No live route options were returned. Try again.')
  } catch (error) {
    if (error instanceof BackendUnavailableError) {
      throw new Error('The connected route service is unavailable.')
    }
    throw error
  }
}

export async function recalculateRoute(
  trip: TripInput,
  activeRouteId: string,
  hazard: { type: HazardType; roadSegmentId: string; observationId: string },
  mode: AppMode = 'live',
): Promise<RouteResult & { changed: boolean }> {
  if (mode === 'presentation') {
    const routes = makePresentationRoutes(trip, activeRouteId)
    const recommendedRouteId = routes.find(route => route.recommended)?.id ?? 'safer'
    return {
      routes,
      source: 'presentation',
      message: 'Route scores recalculated after the confirmed road finding.',
      recommendedRouteId,
      changed: recommendedRouteId !== activeRouteId,
    }
  }

  try {
    const response = await postJson<RecalculateResponse>(appConfig.paths.recalculate, {
      trip,
      active_route_id: activeRouteId,
      hazard_type: hazard.type,
      road_segment_id: hazard.roadSegmentId,
      observation_id: hazard.observationId,
    })
    assertLiveRouteData(response)
    const result = unwrapRouteResponse(response, 'api')
    if (result.routes.length > 0) return { ...result, changed: response.changed ?? false }
    throw new Error('No live route options were returned after the road update.')
  } catch (error) {
    if (error instanceof BackendUnavailableError) {
      throw new Error('The connected route recheck service is unavailable.')
    }
    throw error
  }
}
