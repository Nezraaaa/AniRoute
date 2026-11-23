import { appConfig } from './config'
import { BackendUnavailableError, postJson } from './api'
import { mapDetection, type ApiDetection } from './vision'
import type { CameraScannerStatus, Coordinates, DetectedHazard, HazardType, HazardUploadResult, ScanFrameResult } from '@/types/aniRoute'

interface ScannerResponse {
  detection_available: boolean
  supported_hazards?: HazardType[]
  message: string
}

interface UploadResponse {
  observation_id: string
  status: 'uploaded'
  message: string
  data_source: string
  stored_at?: string
  evidence_stored?: boolean
}

interface ScanFrameResponse {
  detection_available: boolean
  data_source?: string
  detections?: ApiDetection[]
  evidence_frame_data_url?: string | null
  message?: string
  detection: null | {
    detection_id: string
    hazard_type: HazardType
    label?: string
    source_label?: string
    model?: 'A' | 'B' | 'CV'
    detected_at: string
    confidence?: number
    latitude?: number | null
    longitude?: number | null
    route_id: string
    road_segment_id: string
    distance_ahead_km?: number | null
    frames_seen?: number
  }
}

/** Ask the backend whether real detection is available for this trip. */
export async function startHazardScanning(routeId: string): Promise<CameraScannerStatus> {
  try {
    const result = await postJson<ScannerResponse>(appConfig.paths.scannerStart, { route_id: routeId })
    return {
      detectionAvailable: result.detection_available,
      supportedHazards: result.supported_hazards ?? [],
      message: result.message,
    }
  } catch (error) {
    return {
      detectionAvailable: false,
      message: error instanceof BackendUnavailableError
        ? 'Road detection service is unavailable.'
        : error instanceof Error
          ? error.message
          : 'Road detection is unavailable.',
    }
  }
}

export async function stopHazardScanning(routeId: string): Promise<void> {
  try {
    await postJson(appConfig.paths.scannerStop, { route_id: routeId })
  } catch {
    // Browser media tracks and frame sampling are still stopped locally.
  }
}

export function mapScanFrameResponse(result: ScanFrameResponse): ScanFrameResult {
  const detection = result.detection
  const hazard: DetectedHazard | null = detection
    ? {
        id: detection.detection_id,
        type: detection.hazard_type,
        detectedAt: detection.detected_at,
        confidence: detection.confidence,
        coordinates: detection.latitude != null && detection.longitude != null
          ? { latitude: detection.latitude, longitude: detection.longitude }
          : undefined,
        routeId: detection.route_id,
        roadSegmentId: detection.road_segment_id,
        distanceAheadKm: detection.distance_ahead_km ?? undefined,
        simulated: false,
        label: detection.label,
        sourceLabel: detection.source_label,
        model: detection.model,
        framesSeen: detection.frames_seen,
      }
    : null
  return {
    available: result.detection_available,
    detections: (result.detections ?? []).map(mapDetection),
    hazard,
    evidenceFrame: result.evidence_frame_data_url ?? null,
    message: result.message ?? '',
  }
}

/** Send one camera frame; the server runs both detectors plus 2-of-3 frame smoothing for this route. */
export async function scanCameraFrame(
  routeId: string,
  frameDataUrl: string,
  coordinates?: Coordinates | null,
): Promise<ScanFrameResult> {
  const result = await postJson<ScanFrameResponse>(appConfig.paths.scannerFrame, {
    route_id: routeId,
    captured_at: new Date().toISOString(),
    latitude: coordinates?.latitude,
    longitude: coordinates?.longitude,
    frame_data_url: frameDataUrl,
  })
  return mapScanFrameResponse(result)
}

export async function confirmHazard(
  hazard: DetectedHazard,
  evidenceFrameDataUrl?: string,
): Promise<HazardUploadResult> {

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
      model: hazard.model,
      source_label: hazard.sourceLabel,
      evidence_frame_data_url: evidenceFrameDataUrl,
    })
    if (result.data_source !== 'api') {
      throw new Error('Hazard confirmation is not available from the connected service.')
    }
    return {
      id: result.observation_id,
      status: result.status,
      message: result.message,
      source: 'api',
      storedAt: result.stored_at,
      evidenceStored: result.evidence_stored,
    }
  } catch (error) {
    if (error instanceof BackendUnavailableError) {
      throw new Error('Hazard confirmation service is unavailable.')
    }
    throw error
  }
}
