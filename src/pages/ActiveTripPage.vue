<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowRight, Camera, Check, Clock3, CloudRain, Crosshair, MapPin, Navigation, ShieldCheck, Truck } from '@lucide/vue'
import Alert from '@/components/ui/Alert.vue'
import Badge from '@/components/ui/Badge.vue'
import Button from '@/components/ui/Button.vue'
import Card from '@/components/ui/Card.vue'
import CardContent from '@/components/ui/CardContent.vue'
import CardDescription from '@/components/ui/CardDescription.vue'
import CardHeader from '@/components/ui/CardHeader.vue'
import CardTitle from '@/components/ui/CardTitle.vue'
import CameraPreview from '@/components/active/CameraPreview.vue'
import HazardConfirmation from '@/components/active/HazardConfirmation.vue'
import RouteMap from '@/components/routes/RouteMap.vue'
import { useAniRouteStore } from '@/composables/useAniRouteStore'
import { useCamera } from '@/composables/useCamera'
import { useGeolocation } from '@/composables/useGeolocation'
import { confirmHazard, startHazardScanning, stopHazardScanning } from '@/services/hazards'
import { recalculateRoute } from '@/services/routes'
import type { CameraScannerStatus, Coordinates, DetectedHazard, RouteCategory } from '@/types/aniRoute'

const router = useRouter()
const store = useAniRouteStore()
const camera = useCamera()
const location = useGeolocation()
const scannerStatus = ref<CameraScannerStatus | null>(null)
const cameraStarting = ref(false)
const dialogOpen = ref(false)
const confirmationHazard = ref<DetectedHazard | null>(null)
const pendingDetection = ref<DetectedHazard | null>(null)
const detectedFrame = ref<string | null>(null)
const successMessage = ref('')
const sampleDetectionIndex = ref(0)
const dismissedDetectionIds = new Set<string>()
const route = computed(() => store.activeRoute.value)
const currentLocation = computed(() => location.coordinates.value)
const activeStatus = computed(() => camera.status.value)
const recommendationChanged = computed(() => Boolean(store.state.newRecommendedRouteId && store.state.newRecommendedRouteId !== store.state.activeRouteId))
const newRecommendedRoute = computed(() => store.routes.find(item => item.id === store.state.newRecommendedRouteId) ?? null)
const cameraPreview = ref<{ captureFrame: (maxWidth?: number, quality?: number) => string | undefined } | null>(null)
let detectionTimer: number | undefined

function updateDraggedPoint(field: 'origin' | 'destination', coordinates: Coordinates, index?: number) {
  if (field === 'origin') store.state.originCoordinates = coordinates
  else {
    const pointIndex = index ?? Math.max(store.trip.deliveryPoints.length - 1, 0)
    while (store.state.deliveryPointCoordinates.length <= pointIndex) store.state.deliveryPointCoordinates.push(null)
    store.state.deliveryPointCoordinates[pointIndex] = coordinates
    store.state.destinationCoordinates = store.state.deliveryPointCoordinates
      .filter((point): point is Coordinates => Boolean(point))
      .at(-1) ?? null
  }
}

const categoryLabels: Record<RouteCategory, string> = {
  optimal: 'Optimal route', safer: 'Safer route', fastest: 'Fastest route',
}
const supportedHazards = 'Severe road damage, standing water and road obstructions.'
const demoVisionSamples: Array<{
  type: DetectedHazard['type']
  confidence: number
  distanceAheadKm: number
}> = [
  { type: 'road_obstruction', confidence: 0.92, distanceAheadKm: 0.35 },
  { type: 'standing_water', confidence: 0.87, distanceAheadKm: 0.55 },
  { type: 'severe_road_damage', confidence: 0.84, distanceAheadKm: 0.7 },
]
const detectionLabels: Record<DetectedHazard['type'], string> = {
  pothole: 'Pothole',
  severe_road_damage: 'Severe road damage',
  standing_water: 'Standing water',
  road_obstruction: 'Road obstruction',
}

async function turnCameraOn() {
  cameraStarting.value = true
  const opened = await camera.start()
  if (opened && store.state.activeRouteId) {
    scannerStatus.value = await startHazardScanning(store.state.activeRouteId, store.state.mode)
    if (store.state.mode === 'demo') scheduleDemoDetection()
  }
  cameraStarting.value = false
}

function presentHazard(hazard: DetectedHazard) {
  if (dismissedDetectionIds.has(hazard.id) || confirmationHazard.value) return
  pendingDetection.value = null
  confirmationHazard.value = hazard
  store.state.hazard = hazard
  store.state.uploadStatus = 'idle'
  store.state.uploadMessage = ''
  dialogOpen.value = true
}

function showSampleDetection() {
  if (store.state.mode !== 'demo' || !camera.isOn.value || !store.state.activeRouteId) return
  if (confirmationHazard.value) return
  detectedFrame.value = null
  const sample = demoVisionSamples[sampleDetectionIndex.value % demoVisionSamples.length]!
  sampleDetectionIndex.value += 1
  const id = `sample-${Date.now()}`
  pendingDetection.value = {
    id,
    type: sample.type,
    detectedAt: new Date().toISOString(),
    confidence: sample.confidence,
    coordinates: location.coordinates.value ? { ...location.coordinates.value } : undefined,
    routeId: store.state.activeRouteId,
    roadSegmentId: `${store.state.activeRouteId}-demo-vision-${sampleDetectionIndex.value}`,
    distanceAheadKm: sample.distanceAheadKm,
    simulated: true,
  }
}

function reviewDetectedFinding() {
  if (!pendingDetection.value) return
  detectedFrame.value = cameraPreview.value?.captureFrame(480, 0.55) ?? null
  presentHazard(pendingDetection.value)
}

function scheduleDemoDetection() {
  if (detectionTimer) window.clearTimeout(detectionTimer)
  detectionTimer = window.setTimeout(() => {
    detectionTimer = undefined
    if (store.state.mode === 'demo' && camera.isOn.value && store.state.activeRouteId && !pendingDetection.value && !confirmationHazard.value) showSampleDetection()
  }, 1_400)
}

function detectionConfidence(hazard: DetectedHazard) {
  return hazard.confidence === undefined ? 'Confidence unavailable' : `${Math.round(hazard.confidence * 100)}% confidence`
}

function resumeDemoDetection() {
  detectedFrame.value = null
  if (store.state.mode === 'demo' && camera.isOn.value && store.state.activeRouteId) scheduleDemoDetection()
}

function dismissFinding() {
  if (confirmationHazard.value) dismissedDetectionIds.add(confirmationHazard.value.id)
  dialogOpen.value = false
  confirmationHazard.value = null
  store.state.hazard = null
  store.state.uploadStatus = 'idle'
  store.state.uploadMessage = ''
  resumeDemoDetection()
}

function onDialogOpenChange(open: boolean) {
  if (open) {
    dialogOpen.value = true
    return
  }
  if (store.state.uploadStatus === 'uploading') {
    dialogOpen.value = true
    return
  }
  dismissFinding()
}

async function uploadFinding(evidenceFrameDataUrl?: string) {
  const hazard = confirmationHazard.value
  if (!hazard) return
  store.state.uploadStatus = 'uploading'
  store.state.uploadMessage = ''
  try {
    const upload = await confirmHazard(hazard, evidenceFrameDataUrl, store.state.mode)
    if (upload.status !== 'uploaded') throw new Error(upload.message || 'Road update could not be saved.')
    store.state.uploadStatus = 'uploaded'
    store.state.uploadMessage = upload.message
    dismissedDetectionIds.add(hazard.id)
    dialogOpen.value = false
    confirmationHazard.value = null
    store.state.hazard = null
    resumeDemoDetection()
    successMessage.value = upload.source === 'api'
      ? 'Road update sent. Checking the route again.'
      : 'Road update saved in demo mode. Checking the sample route again.'

    try {
      const result = await recalculateRoute({ ...store.trip }, hazard.routeId, {
        type: hazard.type,
        roadSegmentId: hazard.roadSegmentId,
        observationId: upload.id,
      }, store.state.mode)
      store.replaceRoutes(result.routes)
      store.state.routeSource = result.source
      store.state.newRecommendedRouteId = result.recommendedRouteId
      successMessage.value = result.changed
        ? `${successMessage.value} A different option is now recommended.`
        : `${successMessage.value} The recommendation has been checked.`
      store.state.routeMessage = result.message || ''
    } catch (error) {
      const recheckMessage = error instanceof Error
        ? error.message
        : 'Live route recheck is unavailable.'
      successMessage.value = `Road update sent, but route recheck is unavailable: ${recheckMessage}`
      store.state.routeMessage = recheckMessage
      store.state.apiConnected = false
      store.state.newRecommendedRouteId = null
    }
  } catch (error) {
    store.state.uploadStatus = 'failed'
    store.state.uploadMessage = error instanceof Error ? error.message : 'Road update could not be sent. Try again.'
  }
}

function switchToNewRoute() {
  const next = store.state.newRecommendedRouteId
  if (!next || !store.routes.some(item => item.id === next)) return
  store.state.activeRouteId = next
  store.state.selectedRouteId = next
  store.state.newRecommendedRouteId = null
  successMessage.value = `Now using the ${categoryLabels[store.routes.find(item => item.id === next)?.category ?? 'safer'].toLowerCase()}.`
}

function endTrip() {
  const activeRouteId = store.state.activeRouteId
  if (detectionTimer) window.clearTimeout(detectionTimer)
  detectionTimer = undefined
  if (activeRouteId) void stopHazardScanning(activeRouteId, store.state.mode)
  camera.stop()
  location.stop()
  scannerStatus.value = null
  pendingDetection.value = null
  detectedFrame.value = null
  store.state.activeRouteId = null
  store.state.newRecommendedRouteId = null
  store.state.hazard = null
  void router.replace({ name: 'plan' })
}

watch(() => store.state.mode, (mode, previousMode) => {
  if (mode === previousMode || !store.state.activeRouteId) return
  const activeRouteId = store.state.activeRouteId
  void stopHazardScanning(activeRouteId, previousMode)
  if (detectionTimer) window.clearTimeout(detectionTimer)
  camera.stop()
  location.stop()
  pendingDetection.value = null
  detectedFrame.value = null
  scannerStatus.value = null
  store.state.activeRouteId = null
  store.state.newRecommendedRouteId = null
  if (mode === 'live') {
    store.replaceRoutes([])
    store.state.selectedRouteId = ''
    store.state.routeSource = 'api'
    store.state.apiConnected = false
    store.state.routeMessage = 'Live route and risk services are required. No sample fallback will be used.'
  }
  void router.replace({ name: 'plan' })
})

onMounted(async () => {
  if (!store.state.activeRouteId) {
    void router.replace({ name: 'plan' })
    return
  }
  location.start()
  await turnCameraOn()
})

onBeforeUnmount(() => {
  const activeRouteId = store.state.activeRouteId
  if (detectionTimer) window.clearTimeout(detectionTimer)
  if (activeRouteId) void stopHazardScanning(activeRouteId, store.state.mode)
  camera.stop()
  location.stop()
})
</script>

<template>
  <div v-if="route" class="page-wrap active-trip-page">
    <header class="page-heading active-page-heading">
      <div>
        <Badge variant="default" class="active-trip-badge"><span class="status-pulse"></span> Route active</Badge>
        <h1>Your trip is underway</h1>
        <p>{{ categoryLabels[route.category] }} · {{ store.trip.origin }} to {{ store.trip.destination }}</p>
      </div>
      <Button variant="outline" class="end-trip-button" @click="endTrip">End route</Button>
    </header>

    <Alert v-if="successMessage" class="trip-update-banner">
      <Check :size="19" aria-hidden="true" />
      <div><strong>Route checked</strong><p>{{ successMessage }}</p></div>
    </Alert>

    <Alert v-if="recommendationChanged && newRecommendedRoute" variant="warning" class="route-change-banner">
      <ShieldCheck :size="19" aria-hidden="true" />
      <div class="route-change-copy">
        <strong>{{ categoryLabels[newRecommendedRoute.category] }} is recommended now</strong>
        <p>{{ newRecommendedRoute.explanation }}</p>
      </div>
      <Button size="sm" @click="switchToNewRoute">Switch route</Button>
    </Alert>

    <div class="active-layout">
      <div class="active-map-column">
        <RouteMap
          :routes="store.routes"
          :selected-route-id="store.state.activeRouteId ?? ''"
          :prototype-routes="store.state.mode === 'demo'"
          :trip="store.trip"
          :current-location="currentLocation"
          :origin-coordinates="store.state.originCoordinates"
          :destination-coordinates="store.state.destinationCoordinates"
          :delivery-point-coordinates="store.state.deliveryPointCoordinates"
          active
          @point-dragged="updateDraggedPoint"
        />

        <Card class="guidance-card">
          <CardContent class="guidance-content">
            <div class="guidance-icon"><Navigation :size="20" aria-hidden="true" /></div>
            <div><span class="detail-label">Next direction{{ store.state.mode === 'demo' ? ' · sample' : '' }}</span><strong>Continue toward {{ store.trip.destination }}</strong><p>{{ store.state.mode === 'demo' ? 'Turn-by-turn guidance is not connected in this demo.' : 'Turn-by-turn guidance is not integrated yet.' }}</p></div>
          </CardContent>
        </Card>

        <div class="active-status-row">
          <span v-if="location.status.value === 'available'" class="location-status location-good"><Crosshair :size="16" aria-hidden="true" /> Your location is pinned</span>
          <span v-else-if="location.status.value === 'waiting'" class="location-status"><Crosshair :size="16" aria-hidden="true" /> Waiting for your location…</span>
          <span v-else class="location-status location-missing"><MapPin :size="16" aria-hidden="true" /> Location could not be pinned</span>
          <span v-if="location.status.value === 'denied' || location.status.value === 'unavailable'" class="location-help">Hazard updates can be saved without a map pin. No location is guessed.</span>
        </div>
      </div>

      <aside class="active-detail-column" aria-label="Active route details">
        <Card class="trip-estimate-card">
          <CardHeader>
            <div class="flex items-start justify-between gap-3">
              <div><CardTitle>Trip estimate</CardTitle><CardDescription>At trip start · {{ route.source === 'demo' ? 'demo figures' : 'backend figures' }}</CardDescription></div>
              <Badge variant="outline">{{ route.category === 'optimal' ? 'Optimal' : route.category === 'safer' ? 'Safer' : 'Fastest' }}</Badge>
            </div>
          </CardHeader>
          <CardContent>
            <div class="estimate-grid">
              <div><Clock3 :size="18" aria-hidden="true" /><strong>{{ route.travelTimeMinutes }} min</strong><span>estimated time</span></div>
              <div><MapPin :size="18" aria-hidden="true" /><strong>{{ route.distanceKm.toFixed(1) }} km</strong><span>route distance</span></div>
            </div>
            <p class="estimate-note">{{ route.source === 'demo' ? 'Remaining time and distance are not live. Route guidance is a sample.' : 'Remaining time and distance update when live trip telemetry is integrated.' }}</p>
          </CardContent>
        </Card>

        <Card class="trip-summary-card">
          <CardHeader><CardTitle>What you are carrying</CardTitle></CardHeader>
          <CardContent class="trip-summary-content">
            <div class="summary-line"><span>Crop</span><strong>{{ store.trip.crop }}</strong></div>
            <div class="summary-line"><span>Load</span><strong>{{ store.trip.quantity }} kg</strong></div>
            <div class="summary-line"><span>Vehicle</span><strong><Truck :size="15" aria-hidden="true" /> {{ store.trip.vehicle }}</strong></div>
          </CardContent>
        </Card>

        <Card class="camera-status-card">
          <CardHeader>
            <div class="flex items-start gap-3">
              <span :class="['section-icon', camera.isOn.value ? 'section-icon-active' : '']"><Camera :size="20" aria-hidden="true" /></span>
              <div>
                <CardTitle>Road camera</CardTitle>
                <CardDescription>{{ camera.isOn.value ? 'Camera is on for this route.' : 'Camera starts only during an active route.' }}</CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent class="camera-status-content">
            <CameraPreview ref="cameraPreview" :stream="camera.stream.value" :active="camera.isOn.value" :simulated-finding="Boolean(pendingDetection)" />
            <div class="camera-status-copy">
              <Badge v-if="camera.isOn.value" variant="default">Camera is on</Badge>
              <Badge v-else-if="activeStatus === 'permission-needed' || cameraStarting" variant="warning">Waiting for camera permission</Badge>
              <Badge v-else-if="activeStatus === 'denied'" variant="warning">Camera permission needed</Badge>
              <Badge v-else-if="activeStatus === 'unavailable'" variant="warning">Camera unavailable</Badge>
              <Badge v-else variant="secondary">Camera is off</Badge>

              <p class="camera-state-copy">{{ scannerStatus?.message || (store.state.mode === 'demo' ? 'Demo computer vision runs locally and uses mock detections.' : 'Live computer vision is not integrated yet.') }}</p>
              <button v-if="pendingDetection" type="button" class="cv-detection-alert" @click="reviewDetectedFinding">
                <span class="cv-detection-icon"><ShieldCheck :size="17" aria-hidden="true" /></span>
                <span class="cv-detection-copy">
                  <strong>Computer vision detected a road finding</strong>
                  <span>{{ detectionLabels[pendingDetection.type] }} · {{ detectionConfidence(pendingDetection) }}</span>
                  <small>Tap to review and confirm</small>
                </span>
                <ArrowRight :size="17" aria-hidden="true" />
              </button>
              <p v-if="store.state.mode === 'demo'" class="supported-hazards"><strong>Demo detector can preview:</strong> {{ supportedHazards }}</p>
              <p v-else class="supported-hazards"><strong>Live detector:</strong> backend connection required before road findings can be detected.</p>
              <p v-if="camera.errorMessage.value" class="camera-error-copy" role="status">{{ camera.errorMessage.value }}</p>
              <div v-if="!camera.isOn.value" class="camera-action-row">
                <Button :disabled="cameraStarting" @click="turnCameraOn">{{ cameraStarting ? 'Opening camera…' : activeStatus === 'denied' || activeStatus === 'unavailable' ? 'Retry camera access' : 'Turn on camera' }}</Button>
              </div>
              <div v-else class="camera-action-row">
                <p class="camera-demo-note">{{ store.state.mode === 'demo' ? 'Demo computer vision runs automatically while the camera is on.' : 'Live camera is on, but computer vision is unavailable until the backend is integrated.' }}</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card class="road-condition-card">
          <CardContent class="road-condition-content">
            <CloudRain :size="19" aria-hidden="true" />
            <div><span class="detail-label">Road and weather</span><strong>{{ route.roadConditionSummary }}</strong><p>{{ route.weatherFloodSummary }} · {{ route.temperatureSummary }}</p></div>
          </CardContent>
        </Card>
      </aside>
    </div>

    <HazardConfirmation
      :open="dialogOpen"
      :hazard="confirmationHazard"
      :detected-frame="detectedFrame"
      :upload-status="store.state.uploadStatus"
      :upload-message="store.state.uploadMessage"
      :nearby-name="store.trip.destination"
      @update:open="onDialogOpenChange"
      @dismiss="dismissFinding"
      @confirm="uploadFinding"
    />
  </div>
</template>
