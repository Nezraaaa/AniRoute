import assert from 'node:assert/strict'
import test from 'node:test'

const apiBase = process.env.ANIROUTE_API_URL || 'http://127.0.0.1:8000'
const demoTrip = {
  crop: 'Tomatoes', quantity: 250, unit: 'kg', vehicle: 'Small truck',
  origin: 'Farm pickup point, Tupi', destination: 'Koronadal trading post',
}

async function post(path, body) {
  const response = await fetch(`${apiBase}${path}`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  })
  assert.equal(response.ok, true, `${path} returned ${response.status}`)
  return response.json()
}

test('frontend API contract: trip routes, scanning state, confirmed upload, and recheck', async () => {
  const health = await fetch(`${apiBase}/api/health`)
  assert.equal(health.ok, true, 'start the FastAPI server before integration tests')
  assert.equal((await health.json()).status, 'ok')

  const routeResult = await post('/api/routes/calculate', demoTrip)
  assert.equal(routeResult.data_source, 'demo')
  assert.deepEqual(routeResult.routes.map(route => route.category), ['optimal', 'safer', 'fastest'])
  assert.equal(routeResult.recommended_route_id, 'optimal')

  const scanning = await post('/api/hazards/scanning/start', { route_id: 'optimal' })
  assert.equal(scanning.detection_available, false)
  const frameScan = await post('/api/hazards/scan-frame', {
    route_id: 'optimal', captured_at: '2026-09-20T12:30:00Z',
    latitude: 6.42, longitude: 124.89, frame_data_url: 'data:image/jpeg;base64,/9j/AA==',
  })
  assert.equal(frameScan.detection_available, false)
  assert.equal(frameScan.frame_stored, false)
  const stopped = await post('/api/hazards/scanning/stop', { route_id: 'optimal' })
  assert.equal(stopped.scanning, false)

  const upload = await post('/api/hazards/confirm', {
    hazard_type: 'pothole', detected_at: '2026-09-20T12:30:00Z',
    latitude: 6.42, longitude: 124.89, route_id: 'optimal',
    road_segment_id: 'optimal-segment-2', distance_ahead_km: 0.4,
    simulated: true,
  })
  assert.equal(upload.status, 'uploaded')
  assert.equal(upload.data_source, 'demo')

  const rechecked = await post('/api/routes/recalculate', {
    trip: demoTrip, active_route_id: 'optimal', hazard_type: 'pothole',
    road_segment_id: 'optimal-segment-2', observation_id: upload.observation_id,
  })
  assert.equal(rechecked.changed, true)
  assert.equal(rechecked.recommended_route_id, 'safer')
})
