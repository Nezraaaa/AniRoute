import { afterEach, describe, expect, it, vi } from 'vitest'
import { calculateRoutes, recalculateRoute } from '@/services/routes'
import { confirmHazard, scanCameraFrame } from '@/services/hazards'
import { makePresentationRoutes, presentationTrip } from '@/data/presentation'
import type { DetectedHazard } from '@/types/aniRoute'

function jsonResponse(body: unknown, ok = true) {
  return { ok, status: ok ? 200 : 500, json: async () => body } as Response
}

afterEach(() => {
  vi.unstubAllGlobals()
  localStorage.clear()
})

describe('route service adapter', () => {
  it('changes route ranking when crop sensitivity changes', () => {
    const tomatoRoutes = makePresentationRoutes(presentationTrip)
    const riceRoutes = makePresentationRoutes({
      ...presentationTrip,
      crop: 'Rice',
      cropLoads: [{ name: 'Rice', quantity: 250 }],
    })

    expect(tomatoRoutes.find(route => route.recommended)?.id).toBe('optimal')
    expect(riceRoutes.find(route => route.recommended)?.id).toBe('fastest')
    expect(tomatoRoutes.find(route => route.id === 'fastest')?.cropRiskScore)
      .not.toBe(riceRoutes.find(route => route.id === 'fastest')?.cropRiskScore)
  })

  it('raises the affected road factor and recommends the new lowest-risk route', () => {
    const routes = makePresentationRoutes(presentationTrip, 'optimal')

    expect(routes.find(route => route.id === 'optimal')?.riskFactors.road).toBe(56)
    expect(routes.find(route => route.recommended)?.id).toBe('safer')
  })

  it('updates presentation estimates for edited trips and keeps the corridor geometry stable', () => {
    const baseline = makePresentationRoutes(presentationTrip)
    const edited = makePresentationRoutes({
      ...presentationTrip, crop: 'Leafy vegetables', quantity: 500, vehicle: 'Medium truck',
      origin: 'Baguio farm pickup point', destination: 'Calamba, Laguna trading post',
    })

    expect(edited[0]?.travelTimeMinutes).toBeGreaterThan(baseline[0]!.travelTimeMinutes)
    expect(edited[0]?.distanceKm).toBe(baseline[0]!.distanceKm)
    expect(edited[0]?.cropRiskScore).toBeGreaterThan(baseline[0]!.cropRiskScore!)
    expect(edited[0]?.geometry).toEqual(baseline[0]?.geometry)
  })

  it('keeps presentation mode local instead of requesting a route service', async () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)

    const result = await calculateRoutes(presentationTrip, 'presentation')

    expect(fetchMock).not.toHaveBeenCalled()
    expect(result.source).toBe('presentation')
    expect(result.routes.map(route => route.category)).toEqual(['optimal', 'safer', 'fastest'])
  })

  it('maps route categories and explanations from the backend', async () => {
    const route = {
      route_id: 'optimal', category: 'optimal',
      geometry: { type: 'LineString', coordinates: [[120.596, 16.402], [121.17, 14.21]] },
      travel_time_minutes: 52, distance_km: 30.2,
      road_condition_summary: 'Mostly smooth', weather_flood_summary: 'Low sample exposure', temperature_exposure_summary: 'Mild sample exposure',
      crop_risk_score: 25, crop_risk_label: 'lower', explanation: 'Balances this trip.',
      recommended: true, known_hazards: [],
    }
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({
      routes: [route], data_source: 'api', recommended_route_id: 'optimal', message: 'Live data.',
    }))
    vi.stubGlobal('fetch', fetchMock)

    const result = await calculateRoutes(presentationTrip)

    expect(fetchMock).toHaveBeenCalledOnce()
    expect(result.routes[0]).toMatchObject({ id: 'optimal', category: 'optimal', travelTimeMinutes: 52, cropRiskLabel: 'lower' })
    expect(result.recommendedRouteId).toBe('optimal')
    expect(result.source).toBe('api')
  })

  it('shows a clear live integration error when the API is offline', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('offline')))

    await expect(calculateRoutes(presentationTrip)).rejects.toThrow('connected route service is unavailable')
  })

  it('shows backend request errors instead of masking them as demo routes', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse({ detail: 'Trip could not be calculated.' }, false)))

    await expect(calculateRoutes(presentationTrip)).rejects.toThrow('Trip could not be calculated.')
  })

  it('rejects non-production route data while connected mode is active', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse({
      routes: [], data_source: 'presentation', recommended_route_id: 'optimal',
    })))

    await expect(calculateRoutes(presentationTrip)).rejects.toThrow('did not return production route data')
  })

  it('uses the recalculation endpoint after a hazard confirmation', async () => {
    const safer = {
      route_id: 'safer', category: 'safer',
      geometry: { type: 'LineString', coordinates: [[120.596, 16.402], [121.17, 14.21]] },
      travel_time_minutes: 66, distance_km: 37.8,
      road_condition_summary: 'Fewer rough sections', weather_flood_summary: 'Lower sample exposure', temperature_exposure_summary: 'Lower sample exposure',
      crop_risk_score: 20, crop_risk_label: 'lower', explanation: 'Lower known risk.',
      recommended: true, known_hazards: [],
    }
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({
      routes: [safer], data_source: 'api', recommended_route_id: 'safer', changed: true,
    }))
    vi.stubGlobal('fetch', fetchMock)

    const result = await recalculateRoute(presentationTrip, 'optimal', {
      type: 'pothole', roadSegmentId: 'optimal-segment-2', observationId: 'observation-1',
    })

    expect(JSON.parse(fetchMock.mock.calls[0]?.[1]?.body as string)).toMatchObject({
      active_route_id: 'optimal', hazard_type: 'pothole', road_segment_id: 'optimal-segment-2',
    })
    expect(result.changed).toBe(true)
    expect(result.recommendedRouteId).toBe('safer')
  })
})

describe('hazard service adapter', () => {
  it('sends small active-route frames only to an available scanner contract', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ detection_available: false, detection: null }))
    vi.stubGlobal('fetch', fetchMock)
    const frame = 'data:image/jpeg;base64,/9j/AA=='

    expect(await scanCameraFrame('optimal', frame, { latitude: 14.48, longitude: 121.02 })).toBeNull()
    expect(JSON.parse(fetchMock.mock.calls[0]?.[1]?.body as string)).toMatchObject({
      route_id: 'optimal', frame_data_url: frame, latitude: 14.48, longitude: 121.02,
    })
  })

  it('keeps presentation camera frames local instead of requesting the scanner API', async () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)

    expect(await scanCameraFrame('optimal', 'data:image/jpeg;base64,/9j/AA==', null, 'presentation')).toBeNull()
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('sends the geotag and evidence only when confirmation is called', async () => {
    const hazard: DetectedHazard = {
      id: 'sample-1', type: 'pothole', detectedAt: '2026-09-20T12:30:00.000Z',
      coordinates: { latitude: 14.48, longitude: 121.02 }, routeId: 'optimal',
      roadSegmentId: 'optimal-segment-2', distanceAheadKm: 0.4, simulated: false,
    }
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({
      observation_id: 'saved-1', status: 'uploaded', message: 'Saved to demo API.',
      data_source: 'api', stored_at: '2026-09-20T12:31:00Z', evidence_stored: true,
    }))
    vi.stubGlobal('fetch', fetchMock)

    const result = await confirmHazard(hazard, 'data:image/jpeg;base64,aGVsbG8=')

    const payload = JSON.parse(fetchMock.mock.calls[0]?.[1]?.body as string)
    expect(payload).toMatchObject({
      hazard_type: 'pothole', latitude: 14.48, longitude: 121.02,
      route_id: 'optimal', road_segment_id: 'optimal-segment-2', simulated: false,
    })
    expect(payload.evidence_frame_data_url).toBe('data:image/jpeg;base64,aGVsbG8=')
    expect(result).toMatchObject({ id: 'saved-1', status: 'uploaded', source: 'api', evidenceStored: true })
  })

  it('keeps the presentation camera confirmation disconnected from the backend', async () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    const hazard: DetectedHazard = {
      id: 'demo-cv-1', type: 'road_obstruction', detectedAt: '2026-09-20T12:30:00.000Z',
      routeId: 'optimal', roadSegmentId: 'optimal-demo-vision-1', simulated: true,
    }

    const result = await confirmHazard(hazard, undefined, 'presentation')

    expect(fetchMock).not.toHaveBeenCalled()
    expect(result).toMatchObject({ status: 'uploaded', source: 'local_presentation', evidenceStored: false })
  })

  it('does not label a rejected backend upload as successful', async () => {
    const hazard: DetectedHazard = {
      id: 'sample-2', type: 'pothole', detectedAt: '2026-09-20T12:30:00.000Z',
      coordinates: { latitude: 14.48, longitude: 121.02 }, routeId: 'optimal',
      roadSegmentId: 'optimal-segment-2', simulated: false,
    }
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse({ detail: 'Evidence frame is too large.' }, false)))

    await expect(confirmHazard(hazard, 'data:image/jpeg;base64,aGVsbG8=')).rejects.toThrow('Evidence frame is too large.')
  })

  it('shows a clear live integration error instead of saving locally when the API is offline', async () => {
    const hazard: DetectedHazard = {
      id: 'sample-3', type: 'pothole', detectedAt: '2026-09-20T12:30:00.000Z',
      routeId: 'optimal', roadSegmentId: 'optimal-segment-2', simulated: false,
    }
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('offline')))

    await expect(confirmHazard(hazard)).rejects.toThrow('Hazard confirmation service is unavailable')
    expect(localStorage.getItem('aniroute-road-observations')).toBeNull()
  })
})
