// End-to-end contract test against a running backend:
//   uvicorn backend.main:app --port 8000   (from the repository root)
//   npm run test:integration
import assert from 'node:assert/strict'
import test from 'node:test'

const apiBase = process.env.ANIROUTE_API_URL || 'http://127.0.0.1:8000'
const demoTrip = {
  crop: 'Tomatoes', quantity: 250, unit: 'kg', vehicle: 'Small truck',
  origin: 'Farm pickup point, Tupi', destination: 'Koronadal trading post',
  originCoordinates: { latitude: 6.402, longitude: 124.952 },
  deliveryPointCoordinates: [{ latitude: 6.500, longitude: 124.847 }],
}

async function post(path, body) {
  const response = await fetch(`${apiBase}${path}`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  })
  assert.equal(response.ok, true, `${path} returned ${response.status}`)
  return response.json()
}

async function get(path) {
  const response = await fetch(`${apiBase}${path}`)
  assert.equal(response.ok, true, `${path} returned ${response.status}`)
  return response.json()
}

async function sampleImage() {
  const samples = await get('/api/samples')
  const image = samples.find(item => item.kind === 'image')
  assert.ok(image, 'add at least one image to backend/samples/')
  const response = await fetch(`${apiBase}${image.url}`)
  const bytes = Buffer.from(await response.arrayBuffer())
  return { name: image.name, bytes, dataUrl: `data:image/jpeg;base64,${bytes.toString('base64')}` }
}

test('computer vision: model info, image detection with preprocessing stages, reports', async () => {
  const health = await get('/api/health')
  assert.equal(health.status, 'ok', 'start the FastAPI server before integration tests')
  const info = await get('/api/model/info')
  assert.ok(info.models.A && info.models.B)
  assert.ok(Array.isArray(info.supported_hazards))
  if (!health.live_hazard_detection) return   // no weights on this machine: nothing more to check

  const image = await sampleImage()
  const form = new FormData()
  form.append('file', new Blob([image.bytes], { type: 'image/jpeg' }), image.name)
  form.append('clahe', 'on')
  const response = await fetch(`${apiBase}/api/vision/detect`, { method: 'POST', body: form })
  assert.equal(response.ok, true)
  const result = await response.json()
  assert.ok(Array.isArray(result.detections))
  assert.ok(result.annotated_image.startsWith('data:image/jpeg'))
  assert.deepEqual(result.stages.map(stage => stage.name), ['original', 'clahe', 'letterbox'])
  for (const item of result.detections) {
    assert.ok(['pothole', 'severe_road_damage', 'standing_water', 'road_obstruction'].includes(item.hazard_type))
    assert.ok(item.confidence > 0 && item.confidence <= 1)
    assert.equal(item.box_norm.length, 4)
  }
  const metrics = await get('/api/model/metrics')
  assert.ok(['evaluated', 'pending'].includes(metrics.status))
})

test('trip contract: routes, real frame scanning, confirmed upload and recheck', async () => {
  const routeResult = await post('/api/routes/calculate', demoTrip)
  assert.equal(routeResult.data_source, 'api')
  assert.ok(routeResult.routes.length >= 1)
  assert.ok(routeResult.routes.every(route => route.geometry.type === 'LineString'))
  assert.ok(routeResult.routes.every(route => route.travel_time_minutes > 0 && route.distance_km > 0))
  const routeId = routeResult.recommended_route_id
  assert.ok(routeId)

  const scanning = await post('/api/hazards/scanning/start', { route_id: routeId })
  assert.equal(scanning.mode, 'live')
  if (scanning.detection_available) {
    const image = await sampleImage()
    const frame = { route_id: routeId, captured_at: new Date().toISOString(), latitude: 6.42, longitude: 124.89, frame_data_url: image.dataUrl }
    const first = await post('/api/hazards/scan-frame', frame)
    assert.equal(first.data_source, 'api')
    assert.equal(first.frame_stored, false)
    assert.ok(Array.isArray(first.detections))
    const second = await post('/api/hazards/scan-frame', frame)
    if (second.detections.length) assert.ok(second.detection, 'a hazard seen in 2 of 3 frames must raise an alert')
  }
  const stopped = await post('/api/hazards/scanning/stop', { route_id: routeId })
  assert.equal(stopped.scanning, false)

  // simulated: true keeps this test observation out of live route scoring.
  const upload = await post('/api/hazards/confirm', {
    hazard_type: 'pothole', detected_at: new Date().toISOString(),
    latitude: 6.42, longitude: 124.89, route_id: routeId,
    road_segment_id: `${routeId}@6.4200,124.8900`, simulated: true,
  })
  assert.equal(upload.status, 'uploaded')
  assert.equal(upload.data_source, 'api')

  const rechecked = await post('/api/routes/recalculate', {
    trip: demoTrip, active_route_id: routeId, hazard_type: 'pothole',
    road_segment_id: `${routeId}@6.4200,124.8900`, observation_id: upload.observation_id,
  })
  assert.equal(rechecked.data_source, 'api')
  assert.ok(Array.isArray(rechecked.routes))
  assert.match(rechecked.message, /re-scored/)
})
