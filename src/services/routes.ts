import { makeDemoRoutes } from '@/data/demo'
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

export async function calculateRoutes(trip: TripInput, mode: AppMode = 'live'): Promise<RouteResult> {
  if (mode === 'demo') {
    return {
      routes: makeDemoRoutes(trip), source: 'demo',
      message: 'Demo route options - sample road, weather and risk data only.',
      recommendedRouteId: 'optimal',
    }
  }

  try {
    const response = await postJson<ApiRouteResponse>(appConfig.paths.routes, trip)
    const result = unwrapRouteResponse(response, 'api')
    if (result.routes.length > 0) return result
    throw new Error('No route options were returned. Try again.')
  } catch (error) {
    if (!appConfig.demoMode || !(error instanceof BackendUnavailableError)) throw error
    return {
      routes: makeDemoRoutes(trip), source: 'demo',
      message: 'Backend offline · showing sample route options.',
      recommendedRouteId: 'optimal',
    }
  }
}

export async function recalculateRoute(
  trip: TripInput,
  activeRouteId: string,
  hazard: { type: HazardType; roadSegmentId: string; observationId: string },
  mode: AppMode = 'live',
): Promise<RouteResult & { changed: boolean }> {
  if (mode === 'demo') {
    const routes = makeDemoRoutes(trip, activeRouteId)
    const recommendedRouteId = routes.find(route => route.recommended)?.id ?? 'safer'
    return {
      routes,
      source: 'demo',
      message: 'Demo route checked after the confirmed finding.',
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
    const result = unwrapRouteResponse(response, 'api')
    if (result.routes.length > 0) return { ...result, changed: response.changed ?? false }
    throw new Error('No route options were returned after the road update.')
  } catch (error) {
    if (!appConfig.demoMode || !(error instanceof BackendUnavailableError)) throw error
    const routes = makeDemoRoutes(trip, activeRouteId)
    const recommendedRouteId = routes.find(route => route.recommended)?.id ?? 'safer'
    return {
      routes,
      source: 'demo',
      message: 'Sample route checked after the confirmed finding.',
      recommendedRouteId,
      changed: recommendedRouteId !== activeRouteId,
    }
  }
}
