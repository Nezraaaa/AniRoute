<script setup lang="ts">
import { computed, createVNode, onBeforeUnmount, onMounted, ref, render, shallowRef, watch } from 'vue'
import type { GeoJSONSource, LayerSpecification, Map as MapInstance, Marker as MapMarker, StyleSpecification } from 'maplibre-gl'
import { MapPin, Move } from '@lucide/vue'
import { appConfig, defaultCartoStyleUrl, withCartoBasemapKey } from '@/services/config'
import type { Coordinates, RouteOption, TripInput } from '@/types/aniRoute'

const props = withDefaults(defineProps<{
  routes: RouteOption[]
  selectedRouteId: string
  trip: TripInput
  currentLocation?: Coordinates | null
  originCoordinates?: Coordinates | null
  destinationCoordinates?: Coordinates | null
  active?: boolean
}>(), { currentLocation: null, originCoordinates: null, destinationCoordinates: null, active: false })

const emit = defineEmits<{
  'point-dragged': [field: 'origin' | 'destination', coordinates: Coordinates]
}>()

const mapElement = ref<HTMLDivElement | null>(null)
const map = shallowRef<MapInstance | null>(null)
const unavailable = ref(false)
const mapReady = ref(false)
const fallbackStyleActive = ref(false)
const draggedPoints = ref<{ origin: [number, number] | null; destination: [number, number] | null }>({ origin: null, destination: null })
let mapLibreModule: typeof import('maplibre-gl') | null = null
let markers: MapMarker[] = []
let styleFailureTimer: number | undefined

const categoryColors: Record<string, string> = { optimal: '#0b7a54', safer: '#2563eb', fastest: '#e4572e' }
const hasDemoRoutes = computed(() => props.routes.some(route => route.source === 'demo' || route.source === 'local_demo'))

function cartoRasterStyle(): StyleSpecification {
  return {
    version: 8 as const,
    sources: {
      carto: {
        type: 'raster' as const,
        tiles: [withCartoBasemapKey('https://basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png')],
        tileSize: 256,
        minzoom: 0,
        maxzoom: 20,
        attribution: '<a href="https://carto.com/attributions" target="_blank" rel="noopener noreferrer">© CARTO</a> · <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">© OpenStreetMap contributors</a>',
      },
    },
    layers: [{ id: 'carto-voyager', type: 'raster' as const, source: 'carto' }],
  }
}

function mapStyle(): string | StyleSpecification {
  if (appConfig.mapStyleUrl !== defaultCartoStyleUrl) return appConfig.mapStyleUrl
  return cartoRasterStyle()
}

function uniqueRoutes() {
  const seen = new Set<string>()
  return props.routes.filter(route => {
    const key = JSON.stringify(route.geometry.coordinates)
    if (seen.has(key)) return false
    seen.add(key)
    return true
  })
}

function routeGeoJson() {
  if (!hasMapSelection.value) {
    return { type: 'FeatureCollection' as const, features: [] }
  }

  return {
    type: 'FeatureCollection' as const,
    features: uniqueRoutes().map(route => ({
      type: 'Feature' as const,
      properties: {
        routeId: route.id,
        category: route.category,
        color: categoryColors[route.category],
        selected: route.id === props.selectedRouteId,
        sortOrder: route.id === props.selectedRouteId ? 10 : route.category === 'optimal' ? 3 : route.category === 'safer' ? 2 : 1,
      },
      geometry: { ...route.geometry, coordinates: routeCoordinates(route) },
    })),
  }
}

function displayPlace(value: string, fallback: string) {
  return value.trim() || fallback
}

type MapPoint = [number, number]

const philippinesMapView = {
  center: [121.8, 12.3] as MapPoint,
  zoom: 4.8,
  pitch: 46,
  bearing: -10,
}

function pointFromCoordinates(value: Coordinates | null | undefined): MapPoint | null {
  return value ? [value.longitude, value.latitude] : null
}

function selectedMapPoints() {
  return {
    origin: draggedPoints.value.origin ?? pointFromCoordinates(props.originCoordinates),
    destination: draggedPoints.value.destination ?? pointFromCoordinates(props.destinationCoordinates),
  }
}

const hasMapSelection = computed(() => {
  const { origin, destination } = selectedMapPoints()
  return Boolean(origin || destination)
})

function shiftRouteCoordinates(coordinates: MapPoint[], target: MapPoint, anchor: MapPoint): MapPoint[] {
  const longitudeDelta = target[0] - anchor[0]
  const latitudeDelta = target[1] - anchor[1]
  return coordinates.map(([longitude, latitude]) => [longitude + longitudeDelta, latitude + latitudeDelta])
}

function routeCoordinates(route: RouteOption): MapPoint[] {
  const coordinates = route.geometry.coordinates.map(([longitude, latitude]) => [longitude, latitude] as MapPoint)
  if (!coordinates.length) return coordinates

  const { origin, destination } = selectedMapPoints()
  if (!origin && !destination) return []

  // Keep a single selected point and its route together instead of leaving the
  // rest of the illustrative corridor anchored in the old Mindanao demo area.
  if (origin && !destination) return shiftRouteCoordinates(coordinates, origin, coordinates[0])
  if (!origin && destination) return shiftRouteCoordinates(coordinates, destination, coordinates[coordinates.length - 1])
  if (!origin || !destination || coordinates.length < 2) return [origin ?? coordinates[0], destination ?? coordinates[coordinates.length - 1]]

  const baseStart = coordinates[0]
  const baseEnd = coordinates[coordinates.length - 1]
  const baseDelta: MapPoint = [baseEnd[0] - baseStart[0], baseEnd[1] - baseStart[1]]
  const targetDelta: MapPoint = [destination[0] - origin[0], destination[1] - origin[1]]
  const baseLength = Math.hypot(baseDelta[0], baseDelta[1])
  const targetLength = Math.hypot(targetDelta[0], targetDelta[1])
  if (baseLength < 0.000001 || targetLength < 0.000001) return [origin, destination]

  const baseNormal: MapPoint = [-baseDelta[1] / baseLength, baseDelta[0] / baseLength]
  const targetNormal: MapPoint = [-targetDelta[1] / targetLength, targetDelta[0] / targetLength]
  const categoryBend = route.category === 'safer' ? 0.045 : route.category === 'fastest' ? -0.035 : 0.012

  return coordinates.map((point, index) => {
    const progress = index / (coordinates.length - 1)
    const baseLine: MapPoint = [baseStart[0] + baseDelta[0] * progress, baseStart[1] + baseDelta[1] * progress]
    const baseLateral = ((point[0] - baseLine[0]) * baseNormal[0]) + ((point[1] - baseLine[1]) * baseNormal[1])
    const baseLateralRatio = baseLateral / baseLength
    const lateralRatio = Math.max(-0.22, Math.min(0.22, baseLateralRatio + categoryBend * Math.sin(Math.PI * progress)))
    return [
      origin[0] + targetDelta[0] * progress + targetNormal[0] * targetLength * lateralRatio,
      origin[1] + targetDelta[1] * progress + targetNormal[1] * targetLength * lateralRatio,
    ]
  })
}

function makeLabel(text: string, className: string) {
  const node = document.createElement('span')
  node.className = `map-marker ${className}`
  node.textContent = text
  return node
}

function shortPlaceLabel(prefix: string, place: string) {
  const name = place.trim() || (prefix === 'A' ? 'Origin' : 'Destination')
  return `${prefix} · ${name.length > 18 ? `${name.slice(0, 17)}…` : name}`
}

function makePointLabel(prefix: 'A' | 'B', place: string, className: string) {
  const node = document.createElement('button')
  node.type = 'button'
  node.className = `map-point-marker ${className}`
  node.setAttribute('aria-label', `Drag ${prefix === 'A' ? 'pickup' : 'delivery'} point`)
  node.title = `Drag ${prefix === 'A' ? 'pickup' : 'delivery'} point`

  const icon = document.createElement('span')
  icon.className = 'map-point-icon'
  render(createVNode(MapPin, { size: 18, strokeWidth: 2.4, 'aria-hidden': 'true' }), icon)
  node.append(icon)

  const label = document.createElement('span')
  label.className = 'map-point-label'
  label.textContent = shortPlaceLabel(prefix, place)
  node.append(label)
  return node
}

function createMarkers(shouldFitBounds = true) {
  const instance = map.value
  if (!instance || !mapLibreModule) return
  const { LngLatBounds, Marker } = mapLibreModule
  markers.forEach(marker => marker.remove())
  markers = []

  const { origin, destination } = selectedMapPoints()

  const addPointMarker = (point: 'origin' | 'destination', prefix: 'A' | 'B', place: string, className: string, coordinate: [number, number]) => {
    const marker = new Marker({
      element: makePointLabel(prefix, place, className),
      anchor: 'bottom',
      draggable: true,
    }).setLngLat(coordinate)
    marker.on('dragend', () => {
      const next = marker.getLngLat()
      draggedPoints.value[point] = [next.lng, next.lat]
      emit('point-dragged', point, { latitude: next.lat, longitude: next.lng })
      updateRoutes(false)
    })
    markers.push(marker.addTo(instance))
  }

  if (origin) addPointMarker('origin', 'A', props.trip.origin, 'map-point-marker-start', origin)
  if (destination) addPointMarker('destination', 'B', props.trip.destination, 'map-point-marker-end', destination)

  if (props.currentLocation) {
    markers.push(new Marker({ element: makeLabel('Your location', 'map-marker-current'), anchor: 'center' })
      .setLngLat([props.currentLocation.longitude, props.currentLocation.latitude]).addTo(instance))
  }

  const boundPoints = uniqueRoutes().flatMap(route => routeCoordinates(route))
  if (origin) boundPoints.push(origin)
  if (destination) boundPoints.push(destination)
  if (props.currentLocation) boundPoints.push([props.currentLocation.longitude, props.currentLocation.latitude])
  if (!boundPoints.length || !shouldFitBounds) return

  const bounds = new LngLatBounds(boundPoints[0], boundPoints[0])
  for (const routeOption of uniqueRoutes()) {
    for (const point of routeCoordinates(routeOption)) bounds.extend(point)
  }
  if (props.currentLocation) bounds.extend([props.currentLocation.longitude, props.currentLocation.latitude])
  if (shouldFitBounds) instance.fitBounds(bounds, { padding: 48, maxZoom: 14, duration: 250 })
}

function resetToNeutralView(instance: MapInstance) {
  instance.easeTo({ ...philippinesMapView, duration: 250 })
}

function initialMapView() {
  const { origin, destination } = selectedMapPoints()
  const currentLocation = pointFromCoordinates(props.currentLocation)
  const anchor = origin ?? destination ?? currentLocation
  return anchor
    ? { center: anchor, zoom: 9.6, pitch: 42, bearing: -12 }
    : philippinesMapView
}

function add3dBuildings(instance: MapInstance) {
  if (!instance.getSource('carto') || !instance.getLayer('building') || instance.getLayer('aniroute-3d-buildings')) return
  const buildingLayer: LayerSpecification = {
    id: 'aniroute-3d-buildings',
    type: 'fill-extrusion',
    source: 'carto',
    'source-layer': 'building',
    minzoom: 12,
    paint: {
      'fill-extrusion-color': '#b8b6a9',
      'fill-extrusion-opacity': 0.58,
      'fill-extrusion-height': [
        'interpolate', ['linear'], ['zoom'],
        12, 0,
        15, ['coalesce', ['get', 'render_height'], ['get', 'height'], 8],
      ],
      'fill-extrusion-base': ['coalesce', ['get', 'render_min_height'], ['get', 'min_height'], 0],
      'fill-extrusion-vertical-gradient': true,
    },
  }
  try {
    const beforeLayer = instance.getLayer('building-top') ? 'building-top' : undefined
    instance.addLayer(buildingLayer, beforeLayer)
  } catch {
    // Some custom styles omit the building source-layer; the rest of the map remains usable.
  }
}

function addRouteLayers(instance: MapInstance) {
  const routeSource = instance.getSource('route-lines') as GeoJSONSource | undefined
  if (routeSource) {
    routeSource.setData(routeGeoJson())
  } else {
    instance.addSource('route-lines', { type: 'geojson', data: routeGeoJson() })
  }
  if (!instance.getLayer('route-casing')) {
    instance.addLayer({
      id: 'route-casing', type: 'line', source: 'route-lines',
      layout: {
        'line-cap': 'round',
        'line-join': 'round',
        'line-sort-key': ['get', 'sortOrder'],
        visibility: 'visible',
      },
        paint: {
          'line-color': '#ffffff',
          'line-offset': ['match', ['get', 'category'], 'safer', 10, 'fastest', -10, 0],
          'line-width': ['case', ['get', 'selected'], 15, 12],
          'line-opacity': 0.98,
        },
    })
  }
  if (!instance.getLayer('route-strokes')) {
    instance.addLayer({
      id: 'route-strokes', type: 'line', source: 'route-lines',
      layout: {
        'line-cap': 'round',
        'line-join': 'round',
        'line-sort-key': ['get', 'sortOrder'],
        visibility: 'visible',
      },
        paint: {
          'line-color': ['get', 'color'],
          'line-offset': ['match', ['get', 'category'], 'safer', 10, 'fastest', -10, 0],
          'line-width': ['case', ['get', 'selected'], 9, 6],
          'line-opacity': ['case', ['get', 'selected'], 1, 0.92],
        },
    })
  }
  try {
    instance.moveLayer('route-casing')
    instance.moveLayer('route-strokes')
  } catch {
    // The route layers are already above the CARTO basemap in the normal style.
  }
}

function markStyleReady(instance: MapInstance) {
  mapReady.value = true
  unavailable.value = false
  if (styleFailureTimer) window.clearTimeout(styleFailureTimer)
  add3dBuildings(instance)
  addRouteLayers(instance)
  createMarkers()
}

function switchToRasterFallback(instance: MapInstance) {
  if (fallbackStyleActive.value) {
    unavailable.value = true
    return
  }
  fallbackStyleActive.value = true
  mapReady.value = false
  unavailable.value = false
  if (styleFailureTimer) window.clearTimeout(styleFailureTimer)
  instance.setStyle(cartoRasterStyle())
  styleFailureTimer = window.setTimeout(() => {
    if (!mapReady.value) unavailable.value = true
  }, 8_000)
}

function updateRoutes(shouldFitBounds = true) {
  const instance = map.value
  if (!instance || !mapReady.value) return
  const source = instance.getSource('route-lines') as GeoJSONSource | undefined
  source?.setData(routeGeoJson())
  createMarkers(shouldFitBounds)
  if (!hasMapSelection.value && !props.currentLocation) resetToNeutralView(instance)
}

async function initializeMap() {
  if (!mapElement.value) return
  try {
    mapLibreModule = await import('maplibre-gl')
    if (!mapElement.value) return
    const { Map: MapLibreMap, NavigationControl } = mapLibreModule
    const initialView = initialMapView()
    const instance = new MapLibreMap({
      container: mapElement.value,
      style: mapStyle(),
      center: initialView.center,
      zoom: initialView.zoom,
      pitch: initialView.pitch,
      bearing: initialView.bearing,
      attributionControl: {},
      pitchWithRotate: true,
      touchPitch: true,
    })
    map.value = instance
    instance.addControl(new NavigationControl({ showCompass: true }), 'top-right')
    instance.on('style.load', () => markStyleReady(instance))
    instance.on('error', () => {
      if (!mapReady.value) switchToRasterFallback(instance)
    })
    styleFailureTimer = window.setTimeout(() => {
      if (!mapReady.value) switchToRasterFallback(instance)
    }, 8_000)
  } catch {
    unavailable.value = true
  }
}

onMounted(() => { void initializeMap() })
watch(() => props.routes, () => {
  draggedPoints.value = { origin: null, destination: null }
}, { deep: true })
watch(() => [props.originCoordinates, props.destinationCoordinates], () => {
  draggedPoints.value = { origin: null, destination: null }
}, { deep: true })
watch(() => [props.routes, props.selectedRouteId, props.currentLocation, props.trip.origin, props.trip.destination, props.originCoordinates, props.destinationCoordinates], () => updateRoutes(), { deep: true })
onBeforeUnmount(() => {
  if (styleFailureTimer) window.clearTimeout(styleFailureTimer)
  markers.forEach(marker => marker.remove())
  map.value?.remove()
  map.value = null
})
</script>

<template>
  <section class="map-card" aria-label="Map showing route choices">
    <div class="map-heading">
      <div :class="{ 'map-heading-empty': !trip.origin.trim() && !trip.destination.trim() }">
        <p class="eyebrow">{{ active ? 'Active trip' : 'Route map' }}</p>
        <h2>{{ trip.origin }} <span aria-hidden="true">→</span> {{ trip.destination }}</h2>
      </div>
    </div>
    <div class="map-stage">
      <div ref="mapElement" class="map-canvas" role="region" aria-describedby="map-drag-hint" :aria-label="`Map showing route from ${displayPlace(trip.origin, 'pickup point')} to ${displayPlace(trip.destination, 'delivery point')}`"></div>
      <div v-if="unavailable" class="map-fallback" role="status">
        <strong>Map is unavailable right now.</strong>
        <span>Route choices remain available below.</span>
      </div>
      <div v-if="!unavailable && !mapReady" class="map-loading" role="status">Loading map…</div>
      <div v-if="!unavailable && mapReady && !hasMapSelection && !currentLocation" class="map-empty-state" role="status">
        <MapPin :size="19" aria-hidden="true" />
        <div>
          <strong>Choose pickup and delivery points</strong>
          <span>Search for locations to focus the map.</span>
        </div>
      </div>
    </div>
    <p id="map-drag-hint" class="map-drag-hint"><Move :size="14" aria-hidden="true" /> {{ originCoordinates || destinationCoordinates ? 'Drag the selected location pins to reposition pickup and delivery points.' : 'Select pickup and delivery points to place draggable pins on the map.' }}</p>
    <div class="map-legend" aria-label="Route color legend">
      <span><i class="legend-line legend-optimal"></i> Optimal route</span>
      <span><i class="legend-line legend-safer"></i> Safer route</span>
      <span><i class="legend-line legend-fastest"></i> Fastest route</span>
    </div>
    <p class="map-attribution map-attribution-links">
      &copy; <a href="https://carto.com/attributions" target="_blank" rel="noreferrer">CARTO</a>
      &middot; &copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">OpenStreetMap contributors</a>
      &middot; {{ hasDemoRoutes ? 'Sample route lines; live road directions are not connected.' : 'Live road directions are supplied by the backend.' }}
    </p>
  </section>
</template>
