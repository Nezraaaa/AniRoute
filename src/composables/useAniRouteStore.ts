import { computed, reactive } from 'vue'
import { demoTrip, makeDemoRoutes } from '@/data/demo'
import type { Coordinates, DetectedHazard, RouteOption, TripInput } from '@/types/aniRoute'

const trip = reactive<TripInput>({ ...demoTrip })
const routes = reactive<RouteOption[]>(makeDemoRoutes(trip))
const state = reactive({
  mode: 'demo' as 'demo' | 'live',
  loadingRoutes: false,
  fieldErrors: {} as Record<string, string>,
  selectedRouteId: 'optimal',
  activeRouteId: null as string | null,
  routeSource: 'demo' as 'api' | 'demo' | 'local_demo',
  routeMessage: 'Demo route options - enter pickup and delivery points to reposition the map.',
  hazard: null as DetectedHazard | null,
  uploadStatus: 'idle' as 'idle' | 'uploading' | 'uploaded' | 'failed',
  uploadMessage: '',
  newRecommendedRouteId: null as string | null,
  apiConnected: false,
  originCoordinates: null as Coordinates | null,
  destinationCoordinates: null as Coordinates | null,
})

const selectedRoute = computed(() => routes.find(route => route.id === state.selectedRouteId) ?? routes[0] ?? null)
const activeRoute = computed(() => routes.find(route => route.id === state.activeRouteId) ?? null)

function replaceRoutes(next: RouteOption[]) {
  routes.splice(0, routes.length, ...next)
  if (!routes.some(route => route.id === state.selectedRouteId)) state.selectedRouteId = routes[0]?.id ?? ''
}

function validateTrip(): boolean {
  const errors: Record<string, string> = {}
  if (!trip.crop.trim()) errors.crop = 'Choose a crop.'
  if (!Number.isFinite(trip.quantity) || trip.quantity < 1) errors.quantity = 'Enter a load greater than 0 kg.'
  if (!trip.vehicle.trim()) errors.vehicle = 'Choose a vehicle.'
  if (!trip.origin.trim()) errors.origin = 'Enter the farm or pickup point.'
  if (!trip.destination.trim()) errors.destination = 'Enter the market or delivery point.'
  state.fieldErrors = errors
  return Object.keys(errors).length === 0
}

export function useAniRouteStore() {
  return {
    trip,
    routes,
    state,
    selectedRoute,
    activeRoute,
    replaceRoutes,
    validateTrip,
  }
}
