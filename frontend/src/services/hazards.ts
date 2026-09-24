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
  data_source?: DataSource
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

export async function startHazardScanning(routeId: string, mode: AppMode = 'live'): Promise<CameraScannerStatus> {
  if (mode === 'demo') {
    return {
      mode: 'demo',
      detectionAvailable: true,
      message: 'Demo computer vision is running locally. No backend request is made.',
    }
  }

  try {
    const result = await postJson<ScannerResponse>(appConfig.paths.scannerStart, { route_id: routeId })
    if (result.mode === 'demo') {
      return {
        mode: 'live',
        detectionAvailable: false,
        message: 'Live road detection is not integrated yet. Switch to Demo mode for the local sample detector.',
      }
    }
    return {
      mode: 'live',
      detectionAvailable: result.detection_available,
      message: result.message,
    }
  } catch (error) {
    return {
      mode: 'live',
      detectionAvailable: false,
      message: error instanceof BackendUnavailableError
        ? 'Live road detection backend is unavailable. Start the backend to enable computer vision.'
        : error instanceof Error
          ? error.message
          : 'Live road detection is unavailable.',
    }
  }
}

export async function stopHazardScanning(routeId: string, mode: AppMode = 'live'): Promise<void> {
  if (mode === 'demo') return
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
  mode: AppMode = 'live',
): Promise<DetectedHazard | null> {
  if (mode === 'demo') return null
  const result = await postJson<DetectionResponse>(appConfig.paths.scannerFrame, {
    route_id: routeId,
    captured_at: new Date().toISOString(),
    latitude: coordinates?.latitude,
    longitude: coordinates?.longitude,
    frame_data_url: frameDataUrl,
  })
  if (result.data_source && result.data_source !== 'api') {
    throw new Error('Live road detection is not integrated yet. Switch to Demo mode for the local sample detector.')
  }
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
  if (hazard.simulated) {
    throw new Error('Simulated findings are available only in Demo mode.')
  }

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
    if (result.data_source !== 'api') {
      throw new Error('Live hazard confirmation is not integrated yet. Switch to Demo mode for the local confirmation flow.')
    }
    return {
      id: result.observation_id,
      status: result.status,
      message: result.message,
      source: result.data_source,
      storedAt: result.stored_at,
      evidenceStored: result.evidence_stored,
    }
  } catch (error) {
    if (error instanceof BackendUnavailableError) {
      throw new Error('Live hazard confirmation backend is unavailable. Start the backend or switch to Demo mode.')
    }
    throw error
  }
}
