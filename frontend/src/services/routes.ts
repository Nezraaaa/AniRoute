import type { DataSource, HazardType, RouteOption, RouteResult, TripInput } from '@/types/aniRoute'
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
  crop_risk_score: number | null
  crop_risk_label: RouteOption['cropRiskLabel']
  explanation: string
  recommended: boolean
  extra_minutes?: number
  known_hazards: Array<{
    id: string
    name: string
    coordinates: { latitude: number; longitude: number }
    note: string
    hazard_type?: HazardType
  }>
  risk_factors?: RouteOption['riskFactors']
  crop_profile_summary?: string
}

interface ApiRouteResponse {
  routes: ApiRoute[]
  data_source?: string
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
    cropRiskScore: route.crop_risk_score,
    cropRiskLabel: route.crop_risk_label,
    riskFactors: route.risk_factors ?? { travelTime: 0, distance: 0, crop: 0, road: 0 },
    cropProfileSummary: route.crop_profile_summary ?? 'Crop sensitivity is included in the route score.',
    explanation: route.explanation,
    recommended: route.recommended,
    extraMinutes: route.extra_minutes ?? 0,
    knownHazards: (route.known_hazards ?? []).map(hazard => ({
      id: hazard.id, name: hazard.name, coordinates: hazard.coordinates, note: hazard.note, hazardType: hazard.hazard_type,
    })),
    source,
  }
}

function unwrapRouteResponse(data: ApiRouteResponse): RouteResult {
  const routes = (data.routes ?? []).map(route => mapApiRoute(route, 'api'))
  return {
    routes,
    source: 'api',
    message: data.message,
    recommendedRouteId: data.recommended_route_id ?? routes.find(route => route.recommended)?.id ?? routes[0]?.id ?? '',
  }
}

function assertLiveRouteData(data: ApiRouteResponse) {
  if (data.data_source && data.data_source !== 'api') {
    throw new Error('The connected route engine did not return live route data.')
  }
}

export async function calculateRoutes(trip: TripInput): Promise<RouteResult> {
  try {
    const response = await postJson<ApiRouteResponse>(appConfig.paths.routes, trip)
    assertLiveRouteData(response)
    const result = unwrapRouteResponse(response)
    if (result.routes.length > 0) return result
    throw new Error('No route options were returned. Try again.')
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
): Promise<RouteResult & { changed: boolean }> {
  try {
    const response = await postJson<RecalculateResponse>(appConfig.paths.recalculate, {
      trip,
      active_route_id: activeRouteId,
      hazard_type: hazard.type,
      road_segment_id: hazard.roadSegmentId,
      observation_id: hazard.observationId,
    })
    assertLiveRouteData(response)
    const result = unwrapRouteResponse(response)
    if (result.routes.length > 0) return { ...result, changed: response.changed ?? false }
    throw new Error('No route options were returned after the road update.')
  } catch (error) {
    if (error instanceof BackendUnavailableError) {
      throw new Error('The connected route recheck service is unavailable.')
    }
    throw error
  }
}
