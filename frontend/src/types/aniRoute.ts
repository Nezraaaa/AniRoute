export type RouteCategory = 'optimal' | 'safer' | 'fastest'
export type AppMode = 'demo' | 'live'
export type HazardType = 'pothole' | 'severe_road_damage' | 'standing_water' | 'road_obstruction'
export type RiskLevel = 'lower' | 'moderate' | 'higher'
export type DataSource = 'api' | 'demo' | 'local_demo'

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
  source: 'api' | 'local'
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
}

export interface HazardPin {
  id: string
  name: string
  coordinates: Coordinates
  note: string
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
  weatherFloodSummary: string
  temperatureSummary: string
  cropRiskScore: number | null
  cropRiskLabel: RiskLevel
  explanation: string
  recommended: boolean
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
  mode: 'demo' | 'live'
  detectionAvailable: boolean
  message: string
}

export interface ApiErrorShape {
  detail?: string
  message?: string
}
