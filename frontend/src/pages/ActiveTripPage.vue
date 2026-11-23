<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowRight, Camera, Check, Clock3, Crosshair, Film, MapPin, Navigation, ShieldCheck, Truck } from '@lucide/vue'
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
import { useFrameScanner } from '@/composables/useFrameScanner'
import { useGeolocation } from '@/composables/useGeolocation'
import { confirmHazard, scanCameraFrame, startHazardScanning, stopHazardScanning } from '@/services/hazards'
import { recalculateRoute } from '@/services/routes'
import { fetchSamples, hazardLabels } from '@/services/vision'
import type { CameraScannerStatus, Coordinates, DetectedHazard, RouteCategory, SampleMedia, ScanFrameResult, VisionDetection } from '@/types/aniRoute'

type VideoSource = 'camera' | 'recording'

const router = useRouter()
const store = useAniRouteStore()
const camera = useCamera()
const location = useGeolocation()
const scannerStatus = ref<CameraScannerStatus | null>(null)
const cameraStarting = ref(false)
const dialogOpen = ref(false)
const confirmationHazard = ref<DetectedHazard | null>(null)
const pendingDetection = ref<DetectedHazard | null>(null)
const pendingEvidence = ref<string | null>(null)
const detectedFrame = ref<string | null>(null)
const liveDetections = ref<VisionDetection[]>([])
const videoSource = ref<VideoSource>('camera')
const recording = ref<SampleMedia | null>(null)
const successMessage = ref('')
const dismissedDetectionIds = new Set<string>()
const route = computed(() => store.activeRoute.value)
const currentLocation = computed(() => location.coordinates.value)
const activeStatus = computed(() => camera.status.value)
const recommendationChanged = computed(() => Boolean(store.state.newRecommendedRouteId && store.state.newRecommendedRouteId !== store.state.activeRouteId))
const newRecommendedRoute = computed(() => store.routes.find(item => item.id === store.state.newRecommendedRouteId) ?? null)
const cameraPreview = ref<{ video: HTMLVideoElement | null; captureFrame: (maxWidth?: number, quality?: number) => string | undefined } | null>(null)
const recordingSrc = computed(() => videoSource.value === 'recording' ? recording.value?.url ?? null : null)
const analysisActive = computed(() => camera.isOn.value || Boolean(recordingSrc.value))

const scanner = useFrameScanner<ScanFrameResult>({
  getVideo: () => cameraPreview.value?.video ?? null,
  intervalMs: 600,
  send: frame => scanCameraFrame(store.state.activeRouteId ?? 'unknown-route', frame, currentLocation.value),
  onResult: handleScanResult,
})

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
  optimal: 'Recommended route', fastest: 'Fastest route', safer: 'Safest route', alternative: 'Alternative route',
}
const supportedHazardsText = computed(() => {
  const supported = scannerStatus.value?.supportedHazards ?? []
  return supported.length ? supported.map(type => hazardLabels[type]).join(', ') : 'waiting for the detector'
})

function handleScanResult(result: ScanFrameResult) {
  liveDetections.value = result.detections
  if (!result.available || !result.hazard) return
  if (pendingDetection.value || confirmationHazard.value || dismissedDetectionIds.has(result.hazard.id)) return
  pendingDetection.value = result.hazard
  pendingEvidence.value = result.evidenceFrame
}

async function startDetector() {
  const routeId = store.state.activeRouteId
  if (!routeId) return
  scannerStatus.value = await startHazardScanning(routeId)
  if (scannerStatus.value.detectionAvailable && analysisActive.value) scanner.start()
}

async function turnCameraOn() {
  videoSource.value = 'camera'
  liveDetections.value = []
  cameraStarting.value = true
  await camera.start()
  cameraStarting.value = false
  await startDetector()
}

/** Analyse a recorded drive from backend/samples/ instead of the live camera (real detector, real video). */
async function useRecordedDrive() {
  if (!recording.value) return
  camera.stop()
  liveDetections.value = []
  videoSource.value = 'recording'
  await startDetector()
}

async function loadRecording() {
  try {
    const videos = (await fetchSamples()).filter(item => item.kind === 'video')
    recording.value = videos.find(item => item.demo) ?? videos[0] ?? null
  } catch {
    recording.value = null
  }
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

function reviewDetectedFinding() {
  if (!pendingDetection.value) return
  detectedFrame.value = pendingEvidence.value ?? cameraPreview.value?.captureFrame(480, 0.6) ?? null
  presentHazard(pendingDetection.value)
}

function detectionConfidence(hazard: DetectedHazard) {
  return hazard.confidence === undefined ? 'Confidence unavailable' : `${Math.round(hazard.confidence * 100)}% confidence`
}

function resumeAfterFinding() {
  detectedFrame.value = null
  pendingEvidence.value = null
}

function dismissFinding() {
  if (confirmationHazard.value) dismissedDetectionIds.add(confirmationHazard.value.id)
  dialogOpen.value = false
  confirmationHazard.value = null
  store.state.hazard = null
  store.state.uploadStatus = 'idle'
  store.state.uploadMessage = ''
  resumeAfterFinding()
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
    const upload = await confirmHazard(hazard, evidenceFrameDataUrl)
    if (upload.status !== 'uploaded') throw new Error(upload.message || 'Road update could not be saved.')
    store.state.uploadStatus = 'uploaded'
    store.state.uploadMessage = upload.message
    dismissedDetectionIds.add(hazard.id)
    dialogOpen.value = false
    confirmationHazard.value = null
    store.state.hazard = null
    resumeAfterFinding()
    successMessage.value = 'Road update sent. Checking the route again.'

    try {
      const result = await recalculateRoute({
        ...store.trip,
        originCoordinates: store.state.originCoordinates,
        deliveryPointCoordinates: [...store.state.deliveryPointCoordinates],
      }, hazard.routeId, {
        type: hazard.type,
        roadSegmentId: hazard.roadSegmentId,
        observationId: upload.id,
      })
      store.replaceRoutes(result.routes)
      store.state.routeSource = result.source
      store.state.newRecommendedRouteId = result.recommendedRouteId
      successMessage.value = result.message || (result.changed
        ? `${successMessage.value} A different option is now recommended.`
        : `${successMessage.value} The recommendation has been checked.`)
      store.state.routeMessage = result.message || ''
    } catch (error) {
      const recheckMessage = error instanceof Error
        ? error.message
        : 'Route recheck is unavailable.'
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
  successMessage.value = `Now using the ${categoryLabels[store.routes.find(item => item.id === next)?.category ?? 'optimal'].toLowerCase()}.`
}

function stopAnalysis(routeId: string | null) {
  scanner.stop()
  if (routeId) void stopHazardScanning(routeId)
  camera.stop()
  location.stop()
  liveDetections.value = []
  videoSource.value = 'camera'
}

function endTrip() {
  stopAnalysis(store.state.activeRouteId)
  scannerStatus.value = null
  pendingDetection.value = null
  detectedFrame.value = null
  store.state.activeRouteId = null
  store.state.newRecommendedRouteId = null
  store.state.hazard = null
  void router.replace({ name: 'plan' })
}

onMounted(async () => {
  if (!store.state.activeRouteId) {
    void router.replace({ name: 'plan' })
    return
  }
  location.start()
  void loadRecording()
  await turnCameraOn()
})

onBeforeUnmount(() => stopAnalysis(store.state.activeRouteId))
</script>

<template>
  <div v-if="route" class="page-wrap active-trip-page live-trip">
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
            <div><span class="detail-label">Destination</span><strong>Continue toward {{ store.trip.destination }}</strong><p>{{ route.distanceKm.toFixed(1) }} km on the selected route. Turn-by-turn directions are not included.</p></div>
          </CardContent>
        </Card>

        <div class="active-status-row">
          <span v-if="currentLocation" class="location-status location-good"><Crosshair :size="16" aria-hidden="true" /> Vehicle GPS is pinned</span>
          <span v-else-if="location.status.value === 'waiting'" class="location-status"><Crosshair :size="16" aria-hidden="true" /> Waiting for your location…</span>
          <span v-else class="location-status location-missing"><MapPin :size="16" aria-hidden="true" /> Location could not be pinned</span>
          <span v-if="location.status.value === 'denied' || location.status.value === 'unavailable'" class="location-help">Hazards can be saved without a map pin, but only located hazards change route scores. No location is guessed.</span>
        </div>
      </div>

      <aside class="active-detail-column" aria-label="Active route details">
        <Card class="trip-estimate-card">
          <CardHeader>
            <div class="flex items-start justify-between gap-3">
              <div><CardTitle>Trip estimate</CardTitle><CardDescription>Live route estimate</CardDescription></div>
              <Badge variant="outline">{{ route.category === 'optimal' ? 'Recommended' : route.category === 'fastest' ? 'Fastest' : route.category === 'safer' ? 'Safest' : 'Alternative' }}</Badge>
            </div>
          </CardHeader>
          <CardContent>
            <div class="estimate-grid">
              <div><Clock3 :size="18" aria-hidden="true" /><strong>{{ route.travelTimeMinutes }} min</strong><span>estimated time</span></div>
              <div><MapPin :size="18" aria-hidden="true" /><strong>{{ route.distanceKm.toFixed(1) }} km</strong><span>route distance</span></div>
            </div>
            <p class="estimate-note">Risk score reflects the crop, travel time, distance and camera-confirmed road hazards.</p>
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
            <div class="camera-card-heading">
              <div class="flex items-start gap-3">
                <span :class="['section-icon', analysisActive ? 'section-icon-active' : '']"><Camera :size="20" aria-hidden="true" /></span>
                <div>
                  <CardTitle>Road camera</CardTitle>
                  <CardDescription>{{ videoSource === 'recording' ? `Analysing recorded drive: ${recording?.caption || recording?.name}` : camera.isOn.value ? 'Camera is on for this route.' : 'Camera starts only during an active route.' }}</CardDescription>
                </div>
              </div>
              <span class="sensor-edge-status"><span class="sensor-status-dot"></span> {{ scanner.running.value ? 'Detector running' : 'Detector idle' }}</span>
            </div>
          </CardHeader>
          <CardContent class="camera-status-content">
            <div class="camera-sensor-meta">
              <span class="sensor-live-label"><span class="sensor-live-dot"></span> {{ scanner.fps.value ? `Analysing ${scanner.fps.value} frames/s` : scanner.running.value ? 'Analysing frames…' : 'Not analysing' }}</span>
              <span>{{ scanner.latencyMs.value ? `${scanner.latencyMs.value} ms per frame` : 'YOLO11 road-damage model' }}</span>
            </div>
            <CameraPreview
              ref="cameraPreview"
              :stream="videoSource === 'camera' ? camera.stream.value : null"
              :video-src="recordingSrc"
              :detections="liveDetections"
              :active="analysisActive"
            />
            <div class="camera-status-copy">
              <Badge v-if="scanner.running.value" variant="default">Road analysis active</Badge>
              <Badge v-else-if="scannerStatus && !scannerStatus.detectionAvailable" variant="warning">Detector unavailable</Badge>
              <Badge v-else-if="activeStatus === 'permission-needed' || cameraStarting" variant="warning">Waiting for camera permission</Badge>
              <Badge v-else-if="activeStatus === 'denied'" variant="warning">Camera permission needed</Badge>
              <Badge v-else-if="activeStatus === 'unavailable'" variant="warning">Camera unavailable</Badge>
              <Badge v-else variant="secondary">Camera is off</Badge>

              <p class="camera-state-copy">{{ scannerStatus?.message || 'Road-hazard analysis starts automatically for this route.' }}</p>
              <button v-if="pendingDetection" type="button" class="cv-detection-alert" @click="reviewDetectedFinding">
                <span class="cv-detection-icon"><ShieldCheck :size="17" aria-hidden="true" /></span>
                <span class="cv-detection-copy">
                  <strong>Computer vision detected a road hazard</strong>
                  <span>{{ pendingDetection.label || hazardLabels[pendingDetection.type] }} · {{ detectionConfidence(pendingDetection) }}</span>
                  <small>{{ pendingDetection.framesSeen ? `Seen in ${pendingDetection.framesSeen} recent frames · ` : '' }}Tap to review and confirm</small>
                </span>
                <ArrowRight :size="17" aria-hidden="true" />
              </button>
              <p class="supported-hazards"><strong>Detects now:</strong> {{ supportedHazardsText }}. Standing water is driver-reported.</p>
              <p v-if="scanner.lastError.value" class="camera-error-copy" role="status">{{ scanner.lastError.value }}</p>
              <p v-if="camera.errorMessage.value && videoSource === 'camera'" class="camera-error-copy" role="status">{{ camera.errorMessage.value }}</p>
              <div class="camera-action-row">
                <Button v-if="videoSource === 'recording' || !camera.isOn.value" size="sm" :variant="videoSource === 'recording' ? 'outline' : 'default'" :disabled="cameraStarting" @click="turnCameraOn">
                  <Camera :size="15" aria-hidden="true" />
                  {{ cameraStarting ? 'Opening camera…' : videoSource === 'recording' ? 'Use live camera' : activeStatus === 'denied' || activeStatus === 'unavailable' ? 'Retry camera access' : 'Turn on camera' }}
                </Button>
                <Button v-if="recording && videoSource === 'camera'" size="sm" variant="outline" @click="useRecordedDrive">
                  <Film :size="15" aria-hidden="true" /> Analyse recorded drive
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card class="road-condition-card">
          <CardContent class="road-condition-content">
            <Truck :size="19" aria-hidden="true" />
            <div><span class="detail-label">Road</span><strong>{{ route.roadConditionSummary }}</strong></div>
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
