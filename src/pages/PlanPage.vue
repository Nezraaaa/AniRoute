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
import { checkBackend } from '@/services/api'
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
  if (!initial) store.state.loadingRoutes = true
  try {
    await Promise.all([
      resolveLocationCoordinates('origin'),
      resolveLocationCoordinates('destination'),
    ])
    const result = await calculateRoutes({ ...store.trip }, store.state.mode)
    store.replaceRoutes(result.routes)
    store.state.routeSource = result.source
    store.state.routeMessage = result.message || (result.source === 'demo'
      ? 'Sample route options · no live road or weather data.'
      : 'Route options received from AniRoute.')
    store.state.selectedRouteId = result.recommendedRouteId
    store.state.apiConnected = store.state.mode === 'live' && await checkBackend()
  } catch (error) {
    generalError.value = error instanceof Error ? error.message : 'We could not find routes. Check the trip details and try again.'
  } finally {
    store.state.loadingRoutes = false
  }
}

function selectRoute(id: string) {
  store.state.selectedRouteId = id
}

function setPointCoordinates(field: 'origin' | 'destination', coordinates: Coordinates | null) {
  if (field === 'origin') store.state.originCoordinates = coordinates
  else store.state.destinationCoordinates = coordinates
}

function handleLocationSelected(field: 'origin' | 'destination', index: number, location: LocationSuggestion) {
  if (location.latitude === null || location.longitude === null) {
    setPointCoordinates(field, null)
    return
  }
  // The demo map has one draggable delivery endpoint. For multiple stops, use
  // the last non-empty delivery point while the full list stays in the form.
  const lastDestinationIndex = store.trip.deliveryPoints.reduce((last, point, pointIndex) => point.trim() ? pointIndex : last, -1)
  if (field === 'destination' && index !== lastDestinationIndex) return
  setPointCoordinates(field, { latitude: location.latitude, longitude: location.longitude })
}

function handleLocationCleared(field: 'origin' | 'destination', index: number) {
  const lastDestinationIndex = store.trip.deliveryPoints.reduce((last, point, pointIndex) => point.trim() ? pointIndex : last, -1)
  if (field === 'destination' && index !== lastDestinationIndex) return
  setPointCoordinates(field, null)
}

async function resolveLocationCoordinates(field: 'origin' | 'destination') {
  const currentCoordinates = field === 'origin' ? store.state.originCoordinates : store.state.destinationCoordinates
  if (currentCoordinates) return

  const query = field === 'origin'
    ? store.trip.origin
    : (store.trip.deliveryPoints.filter(point => point.trim()).at(-1) || store.trip.destination)
  if (query.trim().length < 2) return

  try {
    const suggestions = await searchLocations(query)
    const match = suggestions.find(location => location.latitude !== null && location.longitude !== null)
    if (match && match.latitude !== null && match.longitude !== null) {
      setPointCoordinates(field, { latitude: match.latitude, longitude: match.longitude })
    }
  } catch {
    // Route planning remains usable with the sample data if geocoding is offline.
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
  document.getElementById('crop')?.focus({ preventScroll: true })
}

onMounted(() => {
  void loadRoutes(true)
})

watch(() => store.state.mode, () => {
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

        <Alert variant="warning" class="demo-banner">
          <Info :size="18" aria-hidden="true" />
          <div>
            <strong>{{ store.state.mode === 'demo' ? 'Demo mode' : store.state.apiConnected ? 'Live mode - backend connected' : 'Live mode - sample fallback' }}</strong>
            <p>{{ store.state.mode === 'demo' ? 'Local route lines and risk levels for layout testing.' : store.state.routeMessage }}</p>
          </div>
        </Alert>

        <section class="route-choice-column" aria-labelledby="route-choice-heading">
          <div class="route-choice-heading">
            <div class="route-choice-copy">
              <h3 id="route-choice-heading" class="route-choice-title">Choose a route</h3>
              <span class="route-choice-subtitle">Expand a route to review details and choose it.</span>
            </div>
          </div>

          <div class="route-choice-panel">
            <Alert v-if="displayRoutes.length === 0" variant="warning" class="empty-routes">
              <Info :size="18" aria-hidden="true" />
              <div><strong>No routes found.</strong><p>Check your delivery details and try again.</p></div>
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

        <p v-if="generalError" class="form-error-banner" role="alert">{{ generalError }}</p>

        <div class="map-column">
          <RouteMap
            :routes="store.routes"
            :selected-route-id="store.state.selectedRouteId"
            :trip="store.trip"
            :origin-coordinates="store.state.originCoordinates"
            :destination-coordinates="store.state.destinationCoordinates"
            @point-dragged="setPointCoordinates"
          />
          <div class="selection-tip"><ArrowRight :size="16" aria-hidden="true" /> Choose any route above. The map follows your selection.</div>
        </div>
      </section>
    </div>
  </div>
</template>
