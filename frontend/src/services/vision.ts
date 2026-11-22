import { appConfig, apiUrl } from './config'
import { getJson, postForm, postJson } from './api'
import type {
  BoxTuple, ClaheMode, DetectResult, DetectionModel, HazardType, ModelInfo, ModelMetrics, ModelStatus,
  PreprocessStage, SampleMedia, VisionDetection,
} from '@/types/aniRoute'

export interface ApiDetection {
  id: string
  hazard_type: HazardType
  label: string
  source_label: string
  confidence: number
  box: BoxTuple
  box_norm: BoxTuple
  model: DetectionModel
}

interface ApiDetectResult {
  detections: ApiDetection[]
  image: { width: number; height: number }
  timings_ms: Record<string, number>
  models_used: DetectionModel[]
  roi_rejected: number
  preprocessing: { clahe_applied: boolean; luminance_mean: number; luminance_std: number }
  annotated_image?: string
  stages?: PreprocessStage[]
}

interface ApiModelStatus {
  name: string
  weights: string
  loaded: boolean
  available: boolean
  runtime_format: string | null
  classes: string[]
  error: string | null
  enabled?: boolean
}

interface ApiModelInfo {
  ready: boolean
  warming_up: boolean
  supported_hazards: HazardType[]
  manual_only_hazards: HazardType[]
  models: { A: ApiModelStatus; B: ApiModelStatus }
  thresholds: { model_a_confidence: number; model_b_confidence: number; nms_iou: number }
  imgsz: number
  device: string
  roi: { top: number; bottom_half_width: number; top_half_width: number; min_height: number }
  smoothing: { window: number; min_hits: number; cooldown_seconds: number; dedupe_meters: number }
  hazard_labels: Record<HazardType, string>
  hazard_colors: Record<HazardType, string>
  evaluated: boolean
}

interface ApiModelMetrics {
  status: 'evaluated' | 'pending'
  reports: Record<string, unknown>
  images: Record<string, string>
  error_gallery: Record<string, Array<{ url: string; caption: string }>>
  error_analysis: string | null
  checked_at: string
}

export const hazardColors: Record<HazardType, string> = {
  pothole: '#F59E0B',
  severe_road_damage: '#DC2626',
  standing_water: '#2563EB',
  road_obstruction: '#7C3AED',
}

export const hazardLabels: Record<HazardType, string> = {
  pothole: 'Pothole',
  severe_road_damage: 'Severe road damage',
  standing_water: 'Standing water',
  road_obstruction: 'Road obstruction',
}

export function mapDetection(item: ApiDetection): VisionDetection {
  return {
    id: item.id,
    hazardType: item.hazard_type,
    label: item.label,
    sourceLabel: item.source_label,
    confidence: item.confidence,
    box: item.box,
    boxNorm: item.box_norm,
    model: item.model,
  }
}

export function mapDetectResult(data: ApiDetectResult): DetectResult {
  return {
    detections: (data.detections ?? []).map(mapDetection),
    image: data.image,
    timingsMs: data.timings_ms ?? {},
    modelsUsed: data.models_used ?? [],
    roiRejected: data.roi_rejected ?? 0,
    preprocessing: {
      claheApplied: Boolean(data.preprocessing?.clahe_applied),
      luminanceMean: data.preprocessing?.luminance_mean ?? 0,
      luminanceStd: data.preprocessing?.luminance_std ?? 0,
    },
    annotatedImage: data.annotated_image,
    stages: data.stages,
  }
}

function mapModelStatus(status: ApiModelStatus): ModelStatus {
  return {
    name: status.name,
    weights: status.weights,
    loaded: status.loaded,
    available: status.available,
    runtimeFormat: status.runtime_format,
    classes: status.classes ?? [],
    error: status.error,
    enabled: status.enabled,
  }
}

export function mapModelInfo(data: ApiModelInfo): ModelInfo {
  return {
    ready: data.ready,
    warmingUp: data.warming_up,
    supportedHazards: data.supported_hazards ?? [],
    manualOnlyHazards: data.manual_only_hazards ?? [],
    models: { A: mapModelStatus(data.models.A), B: mapModelStatus(data.models.B) },
    thresholds: {
      modelAConfidence: data.thresholds.model_a_confidence,
      modelBConfidence: data.thresholds.model_b_confidence,
      nmsIou: data.thresholds.nms_iou,
    },
    imgsz: data.imgsz,
    device: data.device,
    corridor: {
      top: data.roi.top,
      bottomHalfWidth: data.roi.bottom_half_width,
      topHalfWidth: data.roi.top_half_width,
      minHeight: data.roi.min_height,
    },
    smoothing: {
      window: data.smoothing.window,
      minHits: data.smoothing.min_hits,
      cooldownSeconds: data.smoothing.cooldown_seconds,
      dedupeMeters: data.smoothing.dedupe_meters,
    },
    hazardLabels: data.hazard_labels ?? hazardLabels,
    hazardColors: data.hazard_colors ?? hazardColors,
    evaluated: data.evaluated,
  }
}

export async function fetchModelInfo(): Promise<ModelInfo> {
  return mapModelInfo(await getJson<ApiModelInfo>(appConfig.paths.modelInfo, 8_000))
}

export async function fetchModelMetrics(): Promise<ModelMetrics> {
  const data = await getJson<ApiModelMetrics>(appConfig.paths.modelMetrics, 10_000)
  return {
    status: data.status,
    reports: data.reports ?? {},
    images: Object.fromEntries(Object.entries(data.images ?? {}).map(([key, url]) => [key, apiUrl(url)])),
    errorGallery: Object.fromEntries(Object.entries(data.error_gallery ?? {}).map(([key, items]) =>
      [key, items.map(item => ({ url: apiUrl(item.url), caption: item.caption }))])),
    errorAnalysis: data.error_analysis,
    checkedAt: data.checked_at,
  }
}

export async function fetchSamples(): Promise<SampleMedia[]> {
  const items = await getJson<SampleMedia[]>(appConfig.paths.samples, 6_000)
  return items.map(item => ({ ...item, url: apiUrl(item.url) }))
}

export interface DetectOptions {
  conf?: number | null
  clahe?: ClaheMode
  returnStages?: boolean
}

export async function detectImage(file: Blob, filename: string, options: DetectOptions = {}): Promise<DetectResult> {
  const form = new FormData()
  form.append('file', file, filename)
  if (options.conf != null) form.append('conf', String(options.conf))
  form.append('clahe', options.clahe ?? 'auto')
  form.append('return_stages', String(options.returnStages ?? true))
  return mapDetectResult(await postForm<ApiDetectResult>(appConfig.paths.visionDetect, form))
}

export async function detectFrame(frameDataUrl: string, options: DetectOptions & { annotate?: boolean } = {}): Promise<DetectResult> {
  return mapDetectResult(await postJson<ApiDetectResult>(appConfig.paths.visionDetectFrame, {
    frame_data_url: frameDataUrl,
    conf: options.conf ?? undefined,
    clahe: options.clahe ?? 'auto',
    return_stages: options.returnStages ?? false,
    annotate: options.annotate ?? false,
  }))
}

export function formatConfidence(value: number): string {
  return `${Math.round(value * 100)}%`
}
