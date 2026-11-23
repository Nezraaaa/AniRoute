export type RouteCategory = 'optimal' | 'fastest' | 'safer' | 'alternative'
export type HazardType = 'pothole' | 'severe_road_damage' | 'standing_water' | 'road_obstruction'
export type RiskLevel = 'lower' | 'moderate' | 'higher'
export type DataSource = 'api'

export interface Coordinates {
  latitude: number
  longitude: number
}

export interface LocationSuggestion {
  id: string
  displayName: string
  latitude: number | null
  longitude: number | null
  category: string
  type: string
  source: 'api'
}

export interface CropLoad {
  name: string
  quantity: number
}

export interface TripInput {
  crop: string
  quantity: number
  cropLoads: CropLoad[]
  unit: 'kg'
  vehicle: string
  origin: string
  destination: string
  deliveryPoints: string[]
  originCoordinates?: Coordinates | null
  deliveryPointCoordinates?: Array<Coordinates | null>
}

export interface HazardPin {
  id: string
  name: string
  coordinates: Coordinates
  note: string
  hazardType?: HazardType
}

export interface LineGeometry {
  type: 'LineString'
  coordinates: [number, number][]
}

export interface RouteOption {
  id: string
  category: RouteCategory
  categories?: RouteCategory[]
  geometry: LineGeometry
  travelTimeMinutes: number
  distanceKm: number
  roadConditionSummary: string
  cropRiskScore: number | null
  cropRiskLabel: RiskLevel
  riskFactors: {
    travelTime: number
    distance: number
    crop: number
    road: number
    safety: number
  }
  cropProfileSummary: string
  explanation: string
  recommended: boolean
  extraMinutes: number
  knownHazards: HazardPin[]
  source: DataSource
}

export interface DetectedHazard {
  id: string
  type: HazardType
  detectedAt: string
  confidence?: number
  coordinates?: Coordinates
  routeId: string
  roadSegmentId: string
  distanceAheadKm?: number
  evidenceFrameRef?: string
  simulated: boolean
  /** Display label from the detector, e.g. "Road obstruction (cow)". */
  label?: string
  /** Raw class from the model that produced the detection (COCO label for model B). */
  sourceLabel?: string
  model?: 'A' | 'B'
  framesSeen?: number
}

export type UploadStatus = 'idle' | 'uploading' | 'uploaded' | 'failed'

export interface HazardUploadResult {
  id: string
  status: UploadStatus
  message: string
  source: DataSource
  storedAt?: string
  evidenceStored?: boolean
}

export interface RouteResult {
  routes: RouteOption[]
  source: DataSource
  message?: string
  recommendedRouteId: string
}

export interface CameraScannerStatus {
  detectionAvailable: boolean
  message: string
  supportedHazards?: HazardType[]
}

export interface ApiErrorShape {
  detail?: string
  message?: string
}

// ---------------------------------------------------------------------------
// Computer vision (live scanning, evaluation reports)
// ---------------------------------------------------------------------------
export type ClaheMode = 'auto' | 'on' | 'off'
export type DetectionModel = 'A' | 'B'
export type BoxTuple = [number, number, number, number]

export interface VisionDetection {
  id: string
  hazardType: HazardType
  label: string
  sourceLabel: string
  confidence: number
  box: BoxTuple
  boxNorm: BoxTuple
  model: DetectionModel
}

export interface PreprocessStage {
  name: string
  description: string
  applied: boolean
  ms: number
  image: string | null
}

export interface DetectResult {
  detections: VisionDetection[]
  image: { width: number; height: number }
  timingsMs: Record<string, number>
  modelsUsed: DetectionModel[]
  roiRejected: number
  preprocessing: { claheApplied: boolean; luminanceMean: number; luminanceStd: number }
  annotatedImage?: string
  stages?: PreprocessStage[]
}

export interface CorridorSettings {
  top: number
  bottomHalfWidth: number
  topHalfWidth: number
  minHeight: number
}

export interface ModelStatus {
  name: string
  weights: string
  loaded: boolean
  available: boolean
  runtimeFormat: string | null
  classes: string[]
  error: string | null
  enabled?: boolean
}

export interface ModelInfo {
  ready: boolean
  warmingUp: boolean
  supportedHazards: HazardType[]
  manualOnlyHazards: HazardType[]
  models: { A: ModelStatus; B: ModelStatus }
  thresholds: { modelAConfidence: number; modelBConfidence: number; nmsIou: number }
  imgsz: number
  device: string
  corridor: CorridorSettings
  smoothing: { window: number; minHits: number; cooldownSeconds: number; dedupeMeters: number }
  hazardLabels: Record<HazardType, string>
  hazardColors: Record<HazardType, string>
  evaluated: boolean
}

export interface SampleMedia {
  name: string
  kind: 'image' | 'video'
  url: string
  caption: string
  source: string
  demo: boolean
}

export interface GalleryItem {
  url: string
  caption: string
}

export interface ModelMetrics {
  status: 'evaluated' | 'pending'
  // Report JSON files are rendered as-is; their shapes are documented in ml/evaluate.py.
  reports: Record<string, any>
  images: Record<string, string>
  errorGallery: Record<string, GalleryItem[]>
  errorAnalysis: string | null
  checkedAt: string
}

export interface ScanFrameResult {
  available: boolean
  detections: VisionDetection[]
  hazard: DetectedHazard | null
  evidenceFrame: string | null
  latencyMs?: number
  message: string
}
