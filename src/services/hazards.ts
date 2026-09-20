import { appConfig } from './config'
import { BackendUnavailableError, postJson } from './api'
import type { AppMode, CameraScannerStatus, Coordinates, DataSource, DetectedHazard, HazardUploadResult } from '@/types/aniRoute'

interface ScannerResponse {
  mode: 'demo' | 'live'
  detection_available: boolean
  message: string
}

interface UploadResponse {
  observation_id: string
  status: 'uploaded'
  message: string
  data_source: DataSource
  stored_at?: string
  evidence_stored?: boolean
}

interface DetectionResponse {
  detection_available: boolean
  detection: null | {
    detection_id: string
    hazard_type: DetectedHazard['type']
    detected_at: string
    confidence?: number
    latitude?: number
    longitude?: number
    route_id: string
    road_segment_id: string
    distance_ahead_km?: number
  }
}

export async function startHazardScanning(routeId: string): Promise<CameraScannerStatus> {
  try {
    const result = await postJson<ScannerResponse>(appConfig.paths.scannerStart, { route_id: routeId })
    return {
      mode: result.mode,
      detectionAvailable: result.detection_available,
      message: result.message,
    }
  } catch (error) {
    return {
      mode: 'demo',
      detectionAvailable: false,
      message: error instanceof Error && !(error instanceof BackendUnavailableError)
        ? error.message
        : 'Live road detection is not connected. Use the sample finding to try the confirmation flow.',
    }
  }
}

export async function stopHazardScanning(routeId: string): Promise<void> {
  try {
    await postJson(appConfig.paths.scannerStop, { route_id: routeId })
  } catch {
    // Browser media tracks and active frame sampling are still stopped locally.
  }
}

export async function scanCameraFrame(
  routeId: string,
  frameDataUrl: string,
  coordinates?: Coordinates | null,
): Promise<DetectedHazard | null> {
  const result = await postJson<DetectionResponse>(appConfig.paths.scannerFrame, {
    route_id: routeId,
    captured_at: new Date().toISOString(),
    latitude: coordinates?.latitude,
    longitude: coordinates?.longitude,
    frame_data_url: frameDataUrl,
  })
  const detection = result.detection
  if (!result.detection_available || !detection) return null
  const detectedCoordinates = detection.latitude !== undefined && detection.longitude !== undefined
    ? { latitude: detection.latitude, longitude: detection.longitude }
    : undefined
  return {
    id: detection.detection_id,
    type: detection.hazard_type,
    detectedAt: detection.detected_at,
    confidence: detection.confidence,
    coordinates: detectedCoordinates,
    routeId: detection.route_id,
    roadSegmentId: detection.road_segment_id,
    distanceAheadKm: detection.distance_ahead_km,
    simulated: false,
  }
}

function saveLocalDemo(hazard: DetectedHazard, evidenceFrameDataUrl?: string): HazardUploadResult {
  const id = `local-${hazard.id}`
  const entry = {
    ...hazard,
    evidenceFrameIncluded: Boolean(evidenceFrameDataUrl),
    savedAt: new Date().toISOString(),
  }
  try {
    const previous = JSON.parse(localStorage.getItem('aniroute-demo-road-updates') || '[]') as unknown[]
    localStorage.setItem('aniroute-demo-road-updates', JSON.stringify([...previous, entry].slice(-5)))
  } catch {
    // The active trip remains usable when browser storage is unavailable.
  }
  return {
    id,
    status: 'uploaded',
    message: 'Saved in this browser’s demo only. Start the local API to store road updates on the server.',
    source: 'local_demo',
    evidenceStored: Boolean(evidenceFrameDataUrl),
  }
}

export async function confirmHazard(
  hazard: DetectedHazard,
  evidenceFrameDataUrl?: string,
  mode: AppMode = 'live',
): Promise<HazardUploadResult> {
  if (mode === 'demo') return saveLocalDemo(hazard, evidenceFrameDataUrl)

  try {
    const result = await postJson<UploadResponse>(appConfig.paths.hazardConfirm, {
      hazard_type: hazard.type,
      detected_at: hazard.detectedAt,
      confidence: hazard.confidence,
      latitude: hazard.coordinates?.latitude,
      longitude: hazard.coordinates?.longitude,
      route_id: hazard.routeId,
      road_segment_id: hazard.roadSegmentId,
      distance_ahead_km: hazard.distanceAheadKm,
      simulated: hazard.simulated,
      evidence_frame_data_url: evidenceFrameDataUrl,
    })
    return {
      id: result.observation_id,
      status: result.status,
      message: result.message,
      source: result.data_source,
      storedAt: result.stored_at,
      evidenceStored: result.evidence_stored,
    }
  } catch (error) {
    if (!appConfig.demoMode || !(error instanceof BackendUnavailableError)) throw error
    return saveLocalDemo(hazard, evidenceFrameDataUrl)
  }
}
