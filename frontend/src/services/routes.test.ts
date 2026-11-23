import { afterEach, describe, expect, it, vi } from 'vitest'
import { calculateRoutes, recalculateRoute } from '@/services/routes'
import { confirmHazard, scanCameraFrame } from '@/services/hazards'
import { defaultTrip } from '@/composables/useAniRouteStore'
import type { DetectedHazard } from '@/types/aniRoute'

function jsonResponse(body: unknown, ok = true) {
  return { ok, status: ok ? 200 : 500, json: async () => body } as Response
}

afterEach(() => {
  vi.unstubAllGlobals()
  localStorage.clear()
})

describe('route service adapter', () => {
  it('maps route categories and explanations from the backend', async () => {
    const route = {
      route_id: 'optimal', category: 'optimal',
      geometry: { type: 'LineString', coordinates: [[120.596, 16.402], [121.17, 14.21]] },
      travel_time_minutes: 52, distance_km: 30.2,
      road_condition_summary: 'Mostly smooth',
      crop_risk_score: 25, crop_risk_label: 'lower', explanation: 'Balances this trip.',
      recommended: true, known_hazards: [],
    }
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({
      routes: [route], data_source: 'api', recommended_route_id: 'optimal', message: 'Live data.',
    }))
    vi.stubGlobal('fetch', fetchMock)

    const result = await calculateRoutes(defaultTrip)

    expect(fetchMock).toHaveBeenCalledOnce()
    expect(result.routes[0]).toMatchObject({ id: 'optimal', category: 'optimal', travelTimeMinutes: 52, cropRiskLabel: 'lower' })
    expect(result.recommendedRouteId).toBe('optimal')
    expect(result.source).toBe('api')
  })

  it('shows a clear live integration error when the API is offline', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('offline')))

    await expect(calculateRoutes(defaultTrip)).rejects.toThrow('connected route service is unavailable')
  })

  it('shows backend request errors to the user', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse({ detail: 'Trip could not be calculated.' }, false)))

    await expect(calculateRoutes(defaultTrip)).rejects.toThrow('Trip could not be calculated.')
  })

  it('rejects non-production route data while connected mode is active', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse({
      routes: [], data_source: 'sample', recommended_route_id: 'optimal',
    })))

    await expect(calculateRoutes(defaultTrip)).rejects.toThrow('did not return live route data')
  })

  it('uses the recalculation endpoint after a hazard confirmation', async () => {
    const safer = {
      route_id: 'safer', category: 'safer',
      geometry: { type: 'LineString', coordinates: [[120.596, 16.402], [121.17, 14.21]] },
      travel_time_minutes: 66, distance_km: 37.8,
      road_condition_summary: 'Fewer rough sections',
      crop_risk_score: 20, crop_risk_label: 'lower', explanation: 'Lower known risk.',
      recommended: true, known_hazards: [],
    }
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({
      routes: [safer], data_source: 'api', recommended_route_id: 'safer', changed: true,
    }))
    vi.stubGlobal('fetch', fetchMock)

    const result = await recalculateRoute(defaultTrip, 'optimal', {
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
  it('sends active-route frames with the geotag and reports when no detector is loaded', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ detection_available: false, detection: null, detections: [], data_source: 'api' }))
    vi.stubGlobal('fetch', fetchMock)
    const frame = 'data:image/jpeg;base64,/9j/AA=='

    const result = await scanCameraFrame('optimal', frame, { latitude: 14.48, longitude: 121.02 })
    expect(result.available).toBe(false)
    expect(result.hazard).toBeNull()
    expect(JSON.parse(fetchMock.mock.calls[0]?.[1]?.body as string)).toMatchObject({
      route_id: 'optimal', frame_data_url: frame, latitude: 14.48, longitude: 121.02,
    })
  })

  it('maps overlay boxes and a smoothed, confirmed detection from the scanner', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse({
      detection_available: true,
      data_source: 'api',
      detections: [{
        id: 'd1', hazard_type: 'road_obstruction', label: 'Road obstruction (cow)', source_label: 'cow',
        confidence: 0.88, box: [10, 20, 110, 220], box_norm: [0.1, 0.2, 0.5, 0.9], model: 'B',
      }],
      detection: {
        detection_id: 'd1', hazard_type: 'road_obstruction', label: 'Road obstruction (cow)', source_label: 'cow', model: 'B',
        detected_at: '2026-11-22T10:00:00Z', confidence: 0.88, latitude: 14.2, longitude: 121.1,
        route_id: 'route-1', road_segment_id: 'route-1@14.2000,121.1000', distance_ahead_km: null, frames_seen: 2,
      },
      evidence_frame_data_url: 'data:image/jpeg;base64,ZXZpZGVuY2U=',
    })))

    const result = await scanCameraFrame('route-1', 'data:image/jpeg;base64,/9j/AA==', { latitude: 14.2, longitude: 121.1 })
    expect(result.detections[0]).toMatchObject({ hazardType: 'road_obstruction', sourceLabel: 'cow', boxNorm: [0.1, 0.2, 0.5, 0.9], model: 'B' })
    expect(result.hazard).toMatchObject({
      type: 'road_obstruction', simulated: false, model: 'B', sourceLabel: 'cow', framesSeen: 2,
      coordinates: { latitude: 14.2, longitude: 121.1 }, distanceAheadKm: undefined,
    })
    expect(result.evidenceFrame).toBe('data:image/jpeg;base64,ZXZpZGVuY2U=')
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
