import { afterEach, describe, expect, it, vi } from 'vitest'
import { calculateRoutes, recalculateRoute } from '@/services/routes'
import { confirmHazard, scanCameraFrame } from '@/services/hazards'
import { demoTrip, makeDemoRoutes } from '@/data/demo'
import type { DetectedHazard } from '@/types/aniRoute'

function jsonResponse(body: unknown, ok = true) {
  return { ok, status: ok ? 200 : 500, json: async () => body } as Response
}

afterEach(() => {
  vi.unstubAllGlobals()
  localStorage.clear()
})

describe('route service adapter', () => {
  it('updates demo estimates for edited trips and keeps its corridor limitation visible in the data', () => {
    const baseline = makeDemoRoutes(demoTrip)
    const edited = makeDemoRoutes({
      ...demoTrip, crop: 'Leafy vegetables', quantity: 500, vehicle: 'Medium truck',
      origin: 'Polomolok farm gate', destination: 'General Santos public market',
    })

    expect(edited[0]?.travelTimeMinutes).toBeGreaterThan(baseline[0]!.travelTimeMinutes)
    expect(edited[0]?.distanceKm).toBeGreaterThan(baseline[0]!.distanceKm)
    expect(edited[0]?.cropRiskScore).toBeGreaterThan(baseline[0]!.cropRiskScore!)
    expect(edited[0]?.geometry).toEqual(baseline[0]?.geometry)
  })

  it('keeps demo mode local instead of requesting the live route service', async () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)

    const result = await calculateRoutes(demoTrip, 'demo')

    expect(fetchMock).not.toHaveBeenCalled()
    expect(result.source).toBe('demo')
    expect(result.routes.map(route => route.category)).toEqual(['optimal', 'safer', 'fastest'])
  })

  it('maps route categories and explanations from the backend', async () => {
    const route = {
      route_id: 'optimal', category: 'optimal',
      geometry: { type: 'LineString', coordinates: [[124.9, 6.4], [124.8, 6.5]] },
      travel_time_minutes: 52, distance_km: 30.2,
      road_condition_summary: 'Mostly smooth', weather_flood_summary: 'Low sample exposure', temperature_exposure_summary: 'Mild sample exposure',
      crop_risk_score: 25, crop_risk_label: 'lower', explanation: 'Balances this trip.',
      recommended: true, known_hazards: [],
    }
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({
      routes: [route], data_source: 'demo', recommended_route_id: 'optimal', message: 'Sample data.',
    }))
    vi.stubGlobal('fetch', fetchMock)

    const result = await calculateRoutes(demoTrip)

    expect(fetchMock).toHaveBeenCalledOnce()
    expect(result.routes[0]).toMatchObject({ id: 'optimal', category: 'optimal', travelTimeMinutes: 52, cropRiskLabel: 'lower' })
    expect(result.recommendedRouteId).toBe('optimal')
    expect(result.source).toBe('demo')
  })

  it('uses clearly labelled deterministic demo routes when the API is offline', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('offline')))

    const result = await calculateRoutes(demoTrip)

    expect(result.source).toBe('demo')
    expect(result.message).toMatch(/offline|sample/i)
    expect(result.routes.map(route => route.category)).toEqual(['optimal', 'safer', 'fastest'])
    expect(result.routes.find(route => route.recommended)?.id).toBe('optimal')
  })

  it('shows backend request errors instead of masking them as demo routes', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse({ detail: 'Trip could not be calculated.' }, false)))

    await expect(calculateRoutes(demoTrip)).rejects.toThrow('Trip could not be calculated.')
  })

  it('uses the recalculation endpoint after a hazard confirmation', async () => {
    const safer = {
      route_id: 'safer', category: 'safer',
      geometry: { type: 'LineString', coordinates: [[124.9, 6.4], [124.8, 6.5]] },
      travel_time_minutes: 66, distance_km: 37.8,
      road_condition_summary: 'Fewer rough sections', weather_flood_summary: 'Lower sample exposure', temperature_exposure_summary: 'Lower sample exposure',
      crop_risk_score: 20, crop_risk_label: 'lower', explanation: 'Lower known risk.',
      recommended: true, known_hazards: [],
    }
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({
      routes: [safer], data_source: 'demo', recommended_route_id: 'safer', changed: true,
    }))
    vi.stubGlobal('fetch', fetchMock)

    const result = await recalculateRoute(demoTrip, 'optimal', {
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

    expect(await scanCameraFrame('optimal', frame, { latitude: 6.42, longitude: 124.89 })).toBeNull()
    expect(JSON.parse(fetchMock.mock.calls[0]?.[1]?.body as string)).toMatchObject({
      route_id: 'optimal', frame_data_url: frame, latitude: 6.42, longitude: 124.89,
    })
  })

  it('sends the geotag and evidence only when confirmation is called', async () => {
    const hazard: DetectedHazard = {
      id: 'sample-1', type: 'pothole', detectedAt: '2026-09-20T12:30:00.000Z',
      coordinates: { latitude: 6.42, longitude: 124.89 }, routeId: 'optimal',
      roadSegmentId: 'optimal-segment-2', distanceAheadKm: 0.4, simulated: true,
    }
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({
      observation_id: 'saved-1', status: 'uploaded', message: 'Saved to demo API.',
      data_source: 'demo', stored_at: '2026-09-20T12:31:00Z', evidence_stored: true,
    }))
    vi.stubGlobal('fetch', fetchMock)

    const result = await confirmHazard(hazard, 'data:image/jpeg;base64,aGVsbG8=')

    const payload = JSON.parse(fetchMock.mock.calls[0]?.[1]?.body as string)
    expect(payload).toMatchObject({
      hazard_type: 'pothole', latitude: 6.42, longitude: 124.89,
      route_id: 'optimal', road_segment_id: 'optimal-segment-2', simulated: true,
    })
    expect(payload.evidence_frame_data_url).toBe('data:image/jpeg;base64,aGVsbG8=')
    expect(result).toMatchObject({ id: 'saved-1', status: 'uploaded', source: 'demo', evidenceStored: true })
  })

  it('keeps the demo computer-vision confirmation disconnected from the backend', async () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    const hazard: DetectedHazard = {
      id: 'demo-cv-1', type: 'road_obstruction', detectedAt: '2026-09-20T12:30:00.000Z',
      routeId: 'optimal', roadSegmentId: 'optimal-demo-vision-1', simulated: true,
    }

    const result = await confirmHazard(hazard, undefined, 'demo')

    expect(fetchMock).not.toHaveBeenCalled()
    expect(result).toMatchObject({ status: 'uploaded', source: 'local_demo', evidenceStored: false })
  })

  it('does not label a rejected backend upload as successful', async () => {
    const hazard: DetectedHazard = {
      id: 'sample-2', type: 'pothole', detectedAt: '2026-09-20T12:30:00.000Z',
      coordinates: { latitude: 6.42, longitude: 124.89 }, routeId: 'optimal',
      roadSegmentId: 'optimal-segment-2', simulated: true,
    }
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse({ detail: 'Evidence frame is too large.' }, false)))

    await expect(confirmHazard(hazard, 'data:image/jpeg;base64,aGVsbG8=')).rejects.toThrow('Evidence frame is too large.')
  })

  it('saves a confirmed observation in the browser demo when the API is offline', async () => {
    const hazard: DetectedHazard = {
      id: 'sample-3', type: 'pothole', detectedAt: '2026-09-20T12:30:00.000Z',
      routeId: 'optimal', roadSegmentId: 'optimal-segment-2', simulated: true,
    }
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('offline')))

    const result = await confirmHazard(hazard)

    expect(result).toMatchObject({ status: 'uploaded', source: 'local_demo' })
    expect(JSON.parse(localStorage.getItem('aniroute-demo-road-updates') || '[]')).toHaveLength(1)
  })
})
