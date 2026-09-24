import { computed, reactive } from 'vue'
import { makePresentationRoutes, presentationTrip } from '@/data/presentation'
import type { Coordinates, DetectedHazard, RouteOption, TripInput } from '@/types/aniRoute'

const trip = reactive<TripInput>({
  ...presentationTrip,
  cropLoads: presentationTrip.cropLoads.map(crop => ({ ...crop })),
  deliveryPoints: [...presentationTrip.deliveryPoints],
})
const routes = reactive<RouteOption[]>(makePresentationRoutes(trip))
const state = reactive({
  mode: 'presentation' as 'presentation' | 'live',
  loadingRoutes: false,
  fieldErrors: {} as Record<string, string>,
  selectedRouteId: 'optimal',
  activeRouteId: null as string | null,
  routeSource: 'presentation' as 'api' | 'presentation' | 'local_presentation',
  routeMessage: 'Crop-aware route options are ready for the Baguio-to-Calamba scenario.',
  hazard: null as DetectedHazard | null,
  uploadStatus: 'idle' as 'idle' | 'uploading' | 'uploaded' | 'failed',
  uploadMessage: '',
  newRecommendedRouteId: null as string | null,
  apiConnected: false,
  originCoordinates: { latitude: 16.402, longitude: 120.596 } as Coordinates | null,
  destinationCoordinates: { latitude: 14.2117, longitude: 121.1653 } as Coordinates | null,
  deliveryPointCoordinates: [{ latitude: 14.2117, longitude: 121.1653 }] as Array<Coordinates | null>,
})

const selectedRoute = computed(() => routes.find(route => route.id === state.selectedRouteId) ?? routes[0] ?? null)
const activeRoute = computed(() => routes.find(route => route.id === state.activeRouteId) ?? null)

function replaceRoutes(next: RouteOption[]) {
  routes.splice(0, routes.length, ...next)
  if (!routes.some(route => route.id === state.selectedRouteId)) state.selectedRouteId = routes[0]?.id ?? ''
}

function validateTrip(): boolean {
  const errors: Record<string, string> = {}
  const cropLoads = trip.cropLoads.length
    ? trip.cropLoads
    : trip.crop.trim()
      ? [{ name: trip.crop, quantity: trip.quantity }]
      : []
  const deliveryPoints = trip.deliveryPoints.length
    ? trip.deliveryPoints
    : trip.destination.trim()
      ? [trip.destination]
      : []

  if (!cropLoads.length) errors.crop = 'Add at least one crop type.'
  cropLoads.forEach((crop, index) => {
    if (!crop.name.trim()) errors[`crop-${index}`] = 'Enter a crop name.'
    if (!Number.isFinite(crop.quantity) || crop.quantity < 1) errors[`crop-quantity-${index}`] = 'Enter an amount greater than 0 kg.'
  })
  const totalQuantity = cropLoads.reduce((total, crop) => total + (Number.isFinite(crop.quantity) ? crop.quantity : 0), 0)
  if (cropLoads.length && totalQuantity > 100_000) errors.quantity = 'Total crop quantity cannot exceed 100,000 kg.'
  if (!trip.vehicle.trim()) errors.vehicle = 'Choose a vehicle.'
  if (!trip.origin.trim()) errors.origin = 'Enter the farm or pickup point.'
  if (!deliveryPoints.length) errors.destination = 'Add at least one delivery point.'
  deliveryPoints.forEach((point, index) => {
    if (!point.trim()) errors[`destination-${index}`] = 'Enter a delivery point.'
  })
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
