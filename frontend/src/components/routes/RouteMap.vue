<script setup lang="ts">
import { computed, createVNode, onBeforeUnmount, onMounted, ref, render, shallowRef, watch } from 'vue'
import type { GeoJSONSource, LayerSpecification, Map as MapInstance, Marker as MapMarker, StyleSpecification } from 'maplibre-gl'
import { MapPin } from '@lucide/vue'
import { appConfig, defaultCartoStyleUrl, withCartoBasemapKey } from '@/services/config'
import type { Coordinates, HazardPin, RouteOption, TripInput } from '@/types/aniRoute'

const props = withDefaults(defineProps<{
  routes: RouteOption[]
  selectedRouteId: string
  trip: TripInput
  currentLocation?: Coordinates | null
  originCoordinates?: Coordinates | null
  destinationCoordinates?: Coordinates | null
  deliveryPointCoordinates?: Array<Coordinates | null>
  active?: boolean
  /** Hazards confirmed on this device: pinned even when they are too far from a route to change its score. */
  extraHazards?: HazardPin[]
}>(), { currentLocation: null, originCoordinates: null, destinationCoordinates: null, deliveryPointCoordinates: () => [], active: false, extraHazards: () => [] })

const emit = defineEmits<{
  'point-dragged': [field: 'origin' | 'destination', coordinates: Coordinates, index?: number]
}>()

const mapElement = ref<HTMLDivElement | null>(null)
const map = shallowRef<MapInstance | null>(null)
const unavailable = ref(false)
const mapReady = ref(false)
const fallbackStyleActive = ref(false)
const draggedPoints = ref<{ origin: [number, number] | null; destinations: Record<number, [number, number]> }>({ origin: null, destinations: {} })
let mapLibreModule: typeof import('maplibre-gl') | null = null
let markers: MapMarker[] = []
let styleFailureTimer: number | undefined
// Active trip camera, like turn-by-turn directions: 'follow' = tilted 3D view behind the vehicle,
// 'overview' = the whole route from above. Dragging the map switches to overview until Follow is pressed.
const cameraMode = ref<'follow' | 'overview'>('follow')
const NAV_ZOOM = 16.5
const NAV_PITCH = 60
const LOOK_AHEAD_KM = 0.2

const categoryColors: Record<string, string> = { optimal: '#0b7a54', fastest: '#f97316', safer: '#2563eb', alternative: '#6b7280' }
const routeLayerDefinitions = [
  { category: 'optimal' as const, sourceId: 'route-optimal-source', casingId: 'route-optimal-casing', layerId: 'route-optimal', color: '#0b7a54', offset: 0 },
  { category: 'safer' as const, sourceId: 'route-safer-source', casingId: 'route-safer-casing', layerId: 'route-safer', color: '#2563eb', offset: 0 },
  { category: 'fastest' as const, sourceId: 'route-fastest-source', casingId: 'route-fastest-casing', layerId: 'route-fastest', color: '#f97316', offset: 0 },
  { category: 'alternative' as const, sourceId: 'route-alternative-source', casingId: 'route-alternative-casing', layerId: 'route-alternative', color: '#6b7280', offset: 0 },
]

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

function routeLines(): Array<Pick<RouteOption, 'id' | 'category' | 'geometry' | 'source'>> {
  return uniqueRoutes()
}

function routeGeoJson() {
  return {
    type: 'FeatureCollection' as const,
    features: routeLines().map(route => ({
      type: 'Feature' as const,
      properties: {
        routeId: route.id,
        category: route.category,
        color: categoryColors[route.category],
        selected: route.id === props.selectedRouteId,
        sortOrder: route.id === props.selectedRouteId ? 10 : route.category === 'optimal' ? 3 : route.category === 'fastest' ? 2 : 1,
      },
      geometry: { ...route.geometry, coordinates: routeCoordinates(route) },
    })),
  }
}

function routeGeoJsonFor(category: RouteOption['category']) {
  const features = routeGeoJson().features.filter(feature => feature.properties.category === category)
  return { type: 'FeatureCollection' as const, features }
}

function displayPlace(value: string, fallback: string) {
  return value.trim() || fallback
}

type MapPoint = [number, number]

// Default view: the whole Philippines, flat and centred (Batanes to Mindanao).
const philippinesMapView = {
  center: [122.0, 12.9] as MapPoint,
  zoom: 4.45,
  pitch: 0,
  bearing: 0,
}

function pointFromCoordinates(value: Coordinates | null | undefined): MapPoint | null {
  return value ? [value.longitude, value.latitude] : null
}

function deliveryMapPoints() {
  const points = props.deliveryPointCoordinates
    .map((coordinates, index) => ({
      index,
      coordinate: draggedPoints.value.destinations[index] ?? pointFromCoordinates(coordinates),
    }))
    .filter((item): item is { index: number; coordinate: MapPoint } => Boolean(item.coordinate))

  if (!points.length) {
    const fallback = draggedPoints.value.destinations[0] ?? pointFromCoordinates(props.destinationCoordinates)
    if (fallback) points.push({ index: 0, coordinate: fallback })
  }
  return points
}

function selectedMapPoints() {
  return {
    origin: draggedPoints.value.origin ?? pointFromCoordinates(props.originCoordinates),
    deliveries: deliveryMapPoints(),
  }
}

function selectedWaypoints() {
  const { origin, deliveries } = selectedMapPoints()
  return [
    ...(origin ? [origin] : []),
    ...deliveries.map(item => item.coordinate),
  ]
}

const hasMapSelection = computed(() => selectedWaypoints().length > 0)
const legendCategories = computed(() => new Set(props.routes.map(route => route.category)))

function routeCoordinates(route: Pick<RouteOption, 'geometry'>): MapPoint[] {
  return route.geometry.coordinates.map(([longitude, latitude]) => [longitude, latitude] as MapPoint)
}

function makeLabel(text: string, className: string) {
  const node = document.createElement('span')
  node.className = `map-marker ${className}`
  node.textContent = text
  return node
}

const hazardMarkerColors: Record<string, string> = {
  pothole: '#F59E0B', severe_road_damage: '#DC2626', standing_water: '#2563EB', road_obstruction: '#7C3AED',
}

function makeHazardMarker(name: string, note: string, hazardType?: string) {
  const node = document.createElement('span')
  node.className = 'map-hazard-marker'
  node.style.setProperty('--hazard-color', hazardMarkerColors[hazardType ?? ''] ?? (/water/i.test(name) ? '#2563EB' : '#B45309'))
  node.setAttribute('role', 'img')
  node.setAttribute('aria-label', `${name}: ${note}`)
  node.title = `${name} · ${note}`
  node.textContent = '!'
  const label = document.createElement('span')
  label.className = 'map-hazard-label'
  label.textContent = name
  node.append(label)
  return node
}

function shortPlaceLabel(prefix: string, place: string) {
  const name = place.trim() || (prefix === 'A' ? 'Origin' : 'Destination')
  const short = name.split(",")[0].trim() || name
  return `${prefix} · ${short.length > 24 ? `${short.slice(0, 23)}…` : short}`
}

function deliveryPointLabel(index: number) {
  let value = index + 2
  let label = ''
  while (value > 0) {
    const remainder = (value - 1) % 26
    label = String.fromCharCode(65 + remainder) + label
    value = Math.floor((value - 1) / 26)
  }
  return label
}

function makePointLabel(prefix: string, place: string, className: string) {
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

  const { origin } = selectedMapPoints()
  const destinations = deliveryMapPoints()

  const addPointMarker = (point: 'origin' | 'destination', prefix: string, place: string, className: string, coordinate: [number, number], index?: number) => {
    const marker = new Marker({
      element: makePointLabel(prefix, place, className),
      anchor: 'bottom',
      draggable: true,
    }).setLngLat(coordinate)
    marker.on('dragend', () => {
      const next = marker.getLngLat()
      if (point === 'origin') draggedPoints.value.origin = [next.lng, next.lat]
      else if (index !== undefined) draggedPoints.value.destinations[index] = [next.lng, next.lat]
      emit('point-dragged', point, { latitude: next.lat, longitude: next.lng }, index)
      updateRoutes(false)
    })
    markers.push(marker.addTo(instance))
  }

  if (origin) addPointMarker('origin', 'A', props.trip.origin, 'map-point-marker-start', origin)
  destinations.forEach(({ index, coordinate }) => {
    const place = props.trip.deliveryPoints[index] ?? (index === 0 ? props.trip.destination : '')
    addPointMarker('destination', deliveryPointLabel(index), place, 'map-point-marker-end', coordinate, index)
  })

  if (props.currentLocation) {
    markers.push(new Marker({ element: makeLabel('Your location', 'map-marker-current'), anchor: 'center' })
      .setLngLat([props.currentLocation.longitude, props.currentLocation.latitude]).addTo(instance))
  }

  // Known and camera-confirmed hazards (one pin per observation, even if several routes pass it).
  const pinned = new Set<string>()
  for (const hazard of [...props.routes.flatMap(route => route.knownHazards ?? []), ...props.extraHazards]) {
    if (pinned.has(hazard.id)) continue
    pinned.add(hazard.id)
    markers.push(new Marker({ element: makeHazardMarker(hazard.name, hazard.note, hazard.hazardType), anchor: 'bottom' })
      .setLngLat([hazard.coordinates.longitude, hazard.coordinates.latitude]).addTo(instance))
  }

  const selectedLines = routeLines().filter(route => !props.selectedRouteId || route.id === props.selectedRouteId)
  const boundPoints = selectedLines.flatMap(route => routeCoordinates(route))
  if (origin) boundPoints.push(origin)
  destinations.forEach(({ coordinate }) => boundPoints.push(coordinate))
  // During a trip the camera frames the route itself, never the device's own GPS position.
  if (props.currentLocation && !props.active) boundPoints.push([props.currentLocation.longitude, props.currentLocation.latitude])
  if (!boundPoints.length || !shouldFitBounds) return

  if (props.active && cameraMode.value === 'follow' && followCamera(instance)) return

  const bounds = new LngLatBounds(boundPoints[0], boundPoints[0])
  for (const point of boundPoints) bounds.extend(point)
  if (shouldFitBounds) {
    // Extra top padding: pin labels sit above their point, so the pickup label is never cut off.
    instance.fitBounds(bounds, {
      padding: { top: 96, bottom: 48, left: 64, right: 72 },
      maxZoom: 14,
      pitch: 0,
      bearing: 0,
      duration: props.active ? 800 : 250,
    })
  }
}

function distanceKm(a: MapPoint, b: MapPoint) {
  const toRad = Math.PI / 180
  const h = Math.sin((b[1] - a[1]) * toRad / 2) ** 2
    + Math.cos(a[1] * toRad) * Math.cos(b[1] * toRad) * Math.sin((b[0] - a[0]) * toRad / 2) ** 2
  return 2 * 6371 * Math.asin(Math.sqrt(h))
}

function bearingDeg(a: MapPoint, b: MapPoint) {
  const toRad = Math.PI / 180
  const y = Math.sin((b[0] - a[0]) * toRad) * Math.cos(b[1] * toRad)
  const x = Math.cos(a[1] * toRad) * Math.sin(b[1] * toRad) - Math.sin(a[1] * toRad) * Math.cos(b[1] * toRad) * Math.cos((b[0] - a[0]) * toRad)
  return Math.atan2(y, x) / toRad
}

/** Tilted 3D camera at the start of the route, turned to face the road ahead. */
function followCamera(instance: MapInstance): boolean {
  const route = routeLines().find(item => item.id === props.selectedRouteId) ?? routeLines()[0]
  const line = route ? routeCoordinates(route) : []
  // Follow the trip's own route from its start (the pickup point), not the device's GPS position.
  const anchor = line[0] ?? selectedMapPoints().origin
  if (!anchor) return false
  let bearing = instance.getBearing()
  if (line.length > 1) {
    // Nearest point of the route to the vehicle, then the point ~200 m further along it.
    let nearest = 0
    let best = Infinity
    line.forEach((point, index) => {
      const d = distanceKm(anchor, point)
      if (d < best) { best = d; nearest = index }
    })
    let travelled = 0
    let ahead = line[Math.min(nearest + 1, line.length - 1)]!
    for (let index = nearest; index < line.length - 1 && travelled < LOOK_AHEAD_KM; index += 1) {
      travelled += distanceKm(line[index]!, line[index + 1]!)
      ahead = line[index + 1]!
    }
    if (distanceKm(anchor, ahead) > 0.005) bearing = bearingDeg(anchor, ahead)
  }
  instance.easeTo({ center: anchor, zoom: NAV_ZOOM, pitch: NAV_PITCH, bearing, duration: 1200, essential: true })
  return true
}

function setCameraMode(mode: 'follow' | 'overview') {
  cameraMode.value = mode
  createMarkers(true)
}

function resetToNeutralView(instance: MapInstance) {
  instance.easeTo({ ...philippinesMapView, duration: 250 })
}

function initialMapView() {
  const { origin, deliveries } = selectedMapPoints()
  const currentLocation = pointFromCoordinates(props.currentLocation)
  const anchor = origin ?? deliveries[0]?.coordinate ?? currentLocation
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
  for (const legacyLayerId of ['route-casing', 'route-strokes']) {
    if (instance.getLayer(legacyLayerId)) instance.setLayoutProperty(legacyLayerId, 'visibility', 'none')
  }

  for (const routeLayer of routeLayerDefinitions) {
    const data = routeGeoJsonFor(routeLayer.category)
    const isSelected = data.features.some(feature => feature.properties.routeId === props.selectedRouteId)
    const routeSource = instance.getSource(routeLayer.sourceId) as GeoJSONSource | undefined
    if (routeSource) routeSource.setData(data)
    else instance.addSource(routeLayer.sourceId, { type: 'geojson', data })

    if (!instance.getLayer(routeLayer.casingId)) {
      instance.addLayer({
        id: routeLayer.casingId, type: 'line', source: routeLayer.sourceId,
        minzoom: 0,
        layout: { 'line-cap': 'round', 'line-join': 'round', visibility: 'visible' },
        paint: { 'line-color': '#ffffff', 'line-offset': routeLayer.offset, 'line-width': 16, 'line-opacity': 1 },
      })
    }
    if (!instance.getLayer(routeLayer.layerId)) {
      instance.addLayer({
        id: routeLayer.layerId, type: 'line', source: routeLayer.sourceId,
        minzoom: 0,
        layout: { 'line-cap': 'round', 'line-join': 'round', visibility: 'visible' },
        paint: { 'line-color': routeLayer.color, 'line-offset': routeLayer.offset, 'line-width': 10, 'line-opacity': 1 },
      })
    }
    instance.setPaintProperty(routeLayer.casingId, 'line-width', isSelected ? 12 : 6)
    instance.setPaintProperty(routeLayer.casingId, 'line-opacity', isSelected ? 1 : 0.5)
    instance.setPaintProperty(routeLayer.layerId, 'line-width', isSelected ? 7 : 4)
    instance.setPaintProperty(routeLayer.layerId, 'line-opacity', isSelected ? 1 : 0.55)
  }

  try {
    // Draw the selected route last so it sits on top of the faded alternatives.
    const selectedCategory = props.routes.find(route => route.id === props.selectedRouteId)?.category
    const drawOrder = [...routeLayerDefinitions].sort((a, b) => Number(a.category === selectedCategory) - Number(b.category === selectedCategory))
    for (const routeLayer of drawOrder) {
      instance.setLayoutProperty(routeLayer.casingId, 'visibility', 'visible')
      instance.setLayoutProperty(routeLayer.layerId, 'visibility', 'visible')
      instance.moveLayer(routeLayer.casingId)
      instance.moveLayer(routeLayer.layerId)
    }
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
  addRouteLayers(instance)
  instance.triggerRepaint()
  createMarkers(shouldFitBounds)
  if (!hasMapSelection.value && !props.currentLocation && !routeLines().length) resetToNeutralView(instance)
}

async function initializeMap() {
  if (!mapElement.value) return
  try {
    mapLibreModule = await import('maplibre-gl')
    // MapLibre 6 looks for its worker next to its own bundle, a file Vite never emits; without a worker
    // the GeoJSON route sources never load. Point it at the worker bundled by Vite instead.
    const { default: workerUrl } = await import('maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url')
    mapLibreModule.setWorkerUrl(workerUrl)
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
    const syncMapLayers = () => markStyleReady(instance)
    // Panning by hand during a trip pauses following (like a navigation app) until Follow is pressed.
    instance.on('dragstart', () => { if (props.active) cameraMode.value = 'overview' })
    instance.on('style.load', syncMapLayers)
    instance.on('load', syncMapLayers)
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
  draggedPoints.value = { origin: null, destinations: {} }
}, { deep: true })
watch(() => [props.originCoordinates, props.destinationCoordinates, props.deliveryPointCoordinates], () => {
  draggedPoints.value = { origin: null, destinations: {} }
}, { deep: true })
// A hazard was just confirmed: switch to Overview and fly to its pin, so it is visible even off the route.
watch(() => props.extraHazards.length, (count, previous) => {
  const newest = props.extraHazards[count - 1]
  const instance = map.value
  if (!newest || count <= (previous ?? 0) || !instance) return
  cameraMode.value = 'overview'
  window.setTimeout(() => instance.flyTo({ center: [newest.coordinates.longitude, newest.coordinates.latitude], zoom: 15, pitch: 0, bearing: 0, duration: 1200 }), 350)
})
watch(() => [props.routes, props.extraHazards, props.selectedRouteId, props.currentLocation, props.trip.origin, props.trip.destination, props.trip.deliveryPoints, props.originCoordinates, props.destinationCoordinates, props.deliveryPointCoordinates], () => updateRoutes(), { deep: true })
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
      <div ref="mapElement" class="map-canvas" role="region" :aria-label="`Map showing route from ${displayPlace(trip.origin, 'pickup point')} to ${displayPlace(trip.destination, 'delivery point')}`"></div>
      <div v-if="unavailable" class="map-fallback" role="status">
        <strong>Map is unavailable right now.</strong>
        <span>Route choices remain available below.</span>
      </div>
      <div v-if="!unavailable && !mapReady" class="map-loading" role="status">Loading map…</div>
      <div v-if="active && mapReady" class="map-camera-toggle" role="group" aria-label="Map view">
        <button type="button" :class="{ active: cameraMode === 'follow' }" :aria-pressed="cameraMode === 'follow'" @click="setCameraMode('follow')">3D follow</button>
        <button type="button" :class="{ active: cameraMode === 'overview' }" :aria-pressed="cameraMode === 'overview'" @click="setCameraMode('overview')">Overview</button>
      </div>
      <div v-if="!unavailable && mapReady && !hasMapSelection && !currentLocation && !routeLines().length" class="map-empty-state" role="status">
        <MapPin :size="19" aria-hidden="true" />
        <div>
          <strong>Choose pickup and delivery points</strong>
          <span>Search for locations to focus the map.</span>
        </div>
      </div>
    </div>
    <div v-if="routes.length" class="map-legend" aria-label="Route color legend">
      <span v-if="legendCategories.has('optimal')"><i class="legend-line legend-optimal"></i> Recommended route</span>
      <span v-if="legendCategories.has('safer')"><i class="legend-line legend-safer"></i> Safest route</span>
      <span v-if="legendCategories.has('fastest')"><i class="legend-line legend-fastest"></i> Fastest route</span>
      <span v-if="legendCategories.has('alternative')"><i class="legend-line legend-alternative"></i> Alternative route</span>
      <span class="map-legend-credit">Road directions by OSRM</span>
    </div>
  </section>
</template>
