<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowRight, Info, Pencil, Route as RouteIcon } from '@lucide/vue'
import DeliveryForm from '@/components/delivery/DeliveryForm.vue'
import RouteMap from '@/components/routes/RouteMap.vue'
import RouteOptionCard from '@/components/routes/RouteOptionCard.vue'
import Alert from '@/components/ui/Alert.vue'
import Badge from '@/components/ui/Badge.vue'
import Button from '@/components/ui/Button.vue'
import { useAniRouteStore } from '@/composables/useAniRouteStore'
import { makePresentationRoutes } from '@/data/presentation'
import { searchLocations } from '@/services/geocoding'
import { calculateRoutes } from '@/services/routes'
import type { Coordinates, LocationSuggestion, RouteOption } from '@/types/aniRoute'

const router = useRouter()
const store = useAniRouteStore()
const formPanel = ref<HTMLElement | null>(null)
const generalError = ref('')
const displayRoutes = computed(() => mergeDuplicateRoutes(store.routes))

function mergeDuplicateRoutes(routes: RouteOption[]): RouteOption[] {
  const unique = new Map<string, RouteOption>()
  for (const route of routes) {
    const key = JSON.stringify(route.geometry.coordinates)
    const existing = unique.get(key)
    if (!existing) {
      unique.set(key, { ...route, categories: [...new Set([route.category, ...(route.categories ?? [])])] })
      continue
    }
    existing.categories = [...new Set([...(existing.categories ?? [existing.category]), route.category, ...(route.categories ?? [])])]
    if (route.recommended) {
      existing.recommended = true
      existing.explanation = route.explanation
    }
  }
  return [...unique.values()]
}

async function loadRoutes(initial = false) {
  generalError.value = ''
  if (!store.validateTrip()) {
    if (initial) store.state.fieldErrors = {}
    return
  }
  const requestMode = store.state.mode
  if (!initial) store.state.loadingRoutes = true
  try {
    await Promise.all([
      resolveLocationCoordinates('origin'),
      ...(store.trip.deliveryPoints.length
        ? store.trip.deliveryPoints.map((_, index) => resolveLocationCoordinates('destination', index))
        : [resolveLocationCoordinates('destination')]),
    ])
    if (store.state.mode !== requestMode) return
    const result = await calculateRoutes({ ...store.trip }, requestMode)
    if (store.state.mode !== requestMode) return
    store.replaceRoutes(result.routes)
    store.state.routeSource = result.source
    store.state.routeMessage = result.message || (result.source === 'presentation'
      ? 'Crop-aware route options calculated for this scenario.'
      : 'Route options received from AniRoute.')
    store.state.selectedRouteId = result.recommendedRouteId
    store.state.apiConnected = requestMode === 'live' && result.source === 'api'
  } catch (error) {
    if (store.state.mode !== requestMode) return
    generalError.value = error instanceof Error ? error.message : 'We could not find routes. Check the trip details and try again.'
    store.state.apiConnected = false
    if (store.state.mode === 'live') {
      store.replaceRoutes([])
      store.state.selectedRouteId = ''
      store.state.routeSource = 'api'
      store.state.routeMessage = generalError.value
    }
  } finally {
    store.state.loadingRoutes = false
  }
}

function selectRoute(id: string) {
  store.state.selectedRouteId = id
}

function syncDestinationCoordinateSummary() {
  store.state.destinationCoordinates = store.state.deliveryPointCoordinates
    .map(coordinate => coordinate)
    .filter((coordinate): coordinate is Coordinates => Boolean(coordinate))
    .at(-1) ?? null
}

function setPointCoordinates(field: 'origin' | 'destination', coordinates: Coordinates | null, index?: number) {
  if (field === 'origin') store.state.originCoordinates = coordinates
  else {
    const pointIndex = index ?? Math.max(store.trip.deliveryPoints.length - 1, 0)
    while (store.state.deliveryPointCoordinates.length <= pointIndex) store.state.deliveryPointCoordinates.push(null)
    store.state.deliveryPointCoordinates[pointIndex] = coordinates
    syncDestinationCoordinateSummary()
  }
}

function handleLocationSelected(field: 'origin' | 'destination', index: number, location: LocationSuggestion) {
  if (location.latitude === null || location.longitude === null) {
    setPointCoordinates(field, null, field === 'destination' ? index : undefined)
    return
  }
  setPointCoordinates(field, { latitude: location.latitude, longitude: location.longitude }, field === 'destination' ? index : undefined)
}

function handleLocationCleared(field: 'origin' | 'destination', index: number) {
  setPointCoordinates(field, null, field === 'destination' ? index : undefined)
}

async function resolveLocationCoordinates(field: 'origin' | 'destination', index?: number) {
  if (store.state.mode === 'presentation') return
  const currentCoordinates = field === 'origin'
    ? store.state.originCoordinates
    : index !== undefined
      ? store.state.deliveryPointCoordinates[index]
      : store.state.destinationCoordinates
  if (currentCoordinates) return

  const query = field === 'origin'
    ? store.trip.origin
    : index !== undefined
      ? store.trip.deliveryPoints[index] || ''
      : (store.trip.deliveryPoints.filter(point => point.trim()).at(-1) || store.trip.destination)
  if (query.trim().length < 2) return

  try {
    const suggestions = await searchLocations(query, undefined, 'live')
    const match = suggestions.find(location => location.latitude !== null && location.longitude !== null)
    if (match && match.latitude !== null && match.longitude !== null) {
      setPointCoordinates(field, { latitude: match.latitude, longitude: match.longitude }, index)
    }
  } catch (error) {
    throw new Error(error instanceof Error ? error.message : 'Location search is unavailable for this presentation corridor.')
  }
}

function useRoute(id: string) {
  const route = store.routes.find(item => item.id === id)
  if (!route) return
  store.state.activeRouteId = route.id
  store.state.selectedRouteId = route.id
  store.state.hazard = null
  store.state.uploadStatus = 'idle'
  store.state.uploadMessage = ''
  void router.push({ name: 'active-trip' })
}

function editTrip() {
  formPanel.value?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  document.getElementById('crop-count')?.focus({ preventScroll: true })
}

onMounted(() => {
  void loadRoutes(true)
})

watch(() => store.trip.deliveryPoints.length, (count) => {
  if (store.state.deliveryPointCoordinates.length > count) store.state.deliveryPointCoordinates.splice(count)
  while (store.state.deliveryPointCoordinates.length < count) store.state.deliveryPointCoordinates.push(null)
  syncDestinationCoordinateSummary()
}, { immediate: true })

watch(() => store.state.mode, (mode) => {
  generalError.value = ''
  store.state.apiConnected = false
  if (mode === 'presentation') {
    const presentationRoutes = makePresentationRoutes({
      ...store.trip,
      cropLoads: store.trip.cropLoads.map(crop => ({ ...crop })),
      deliveryPoints: [...store.trip.deliveryPoints],
    })
    store.replaceRoutes(presentationRoutes)
    store.state.routeSource = 'presentation'
    store.state.routeMessage = 'Crop-aware route options calculated for this presentation scenario.'
    store.state.selectedRouteId = presentationRoutes.find(route => route.recommended)?.id ?? 'optimal'
    return
  }

  store.replaceRoutes([])
  store.state.selectedRouteId = ''
  store.state.routeSource = 'api'
    store.state.routeMessage = 'A connected route service is required for production operation.'
  if (store.trip.origin.trim() && store.trip.destination.trim()) void loadRoutes()
})
</script>

<template>
  <div class="page-wrap plan-page">
    <header class="page-heading">
      <div>
        <Badge variant="secondary" class="section-kicker">Farm delivery</Badge>
        <h1>Plan a delivery</h1>
        <p>Compare road options for your crop, load and destination.</p>
      </div>
      <Button variant="outline" class="edit-trip-button" @click="editTrip">
        <Pencil :size="17" aria-hidden="true" /> Edit trip
      </Button>
    </header>

    <div class="planner-layout">
      <aside ref="formPanel" class="trip-form-column" aria-label="Delivery details">
        <DeliveryForm
          :trip="store.trip"
          :errors="store.state.fieldErrors"
          :loading="store.state.loadingRoutes"
          :mode="store.state.mode"
          @find-routes="loadRoutes()"
          @location-selected="handleLocationSelected"
          @location-cleared="handleLocationCleared"
        />
        <div class="crop-guidance">
          <Info :size="17" aria-hidden="true" />
          <p>Route risk is a simple guide from road and weather information. It is not a freshness or spoilage prediction.</p>
        </div>
      </aside>

      <section class="results-column" aria-labelledby="compare-heading">
        <div class="results-topline">
          <div>
            <p class="eyebrow">Trip options</p>
            <h2 id="compare-heading">Compare routes</h2>
          </div>
          <span class="options-count"><RouteIcon :size="16" aria-hidden="true" /> {{ displayRoutes.length }} options</span>
        </div>

        <Alert variant="default" class="presentation-banner">
          <Info :size="18" aria-hidden="true" />
          <div>
            <strong>Crop-aware route analysis</strong>
            <p>Scores combine travel time, distance, road condition, flood exposure, temperature and crop sensitivity.</p>
          </div>
        </Alert>

        <Alert v-if="generalError" variant="danger" class="integration-error-banner" role="alert">
          <Info :size="18" aria-hidden="true" />
          <div><strong>Route calculation unavailable</strong><p>{{ generalError }}</p></div>
        </Alert>

        <section class="route-choice-column" aria-labelledby="route-choice-heading">
          <div class="route-choice-heading">
            <div class="route-choice-copy">
              <h3 id="route-choice-heading" class="route-choice-title">Choose a route</h3>
              <span class="route-choice-subtitle">Select a route to open its details over the map.</span>
            </div>
          </div>

          <div class="route-choice-panel">
            <Alert v-if="displayRoutes.length === 0" variant="warning" class="empty-routes">
              <Info :size="18" aria-hidden="true" />
              <div>
                <strong>No routes found.</strong>
                <p>Check your delivery details and try again.</p>
              </div>
            </Alert>

            <div v-else class="route-list">
              <RouteOptionCard
                v-for="route in displayRoutes"
                :key="route.id"
                :route="route"
                :selected="store.state.selectedRouteId === route.id"
                :crop="store.trip.crop"
                :loading="store.state.loadingRoutes"
                @select="selectRoute"
                @use="useRoute"
              />
            </div>
          </div>
        </section>

        <div class="map-column">
          <RouteMap
            :routes="store.routes"
            :selected-route-id="store.state.selectedRouteId"
            :prototype-routes="store.state.mode === 'presentation'"
            :trip="store.trip"
            :origin-coordinates="store.state.originCoordinates"
            :destination-coordinates="store.state.destinationCoordinates"
            :delivery-point-coordinates="store.state.deliveryPointCoordinates"
            @point-dragged="setPointCoordinates"
          />
          <div class="selection-tip"><ArrowRight :size="16" aria-hidden="true" /> Choose any route above. The map follows your selection.</div>
        </div>
      </section>
    </div>
  </div>
</template>
