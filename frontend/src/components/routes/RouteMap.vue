<script setup lang="ts">
import { computed, createVNode, onBeforeUnmount, onMounted, ref, render, shallowRef, watch } from 'vue'
import type { GeoJSONSource, LayerSpecification, Map as MapInstance, Marker as MapMarker, StyleSpecification } from 'maplibre-gl'
import { MapPin, Move } from '@lucide/vue'
import { presentationRouteGeometry } from '@/data/presentation'
import { appConfig, defaultCartoStyleUrl, withCartoBasemapKey } from '@/services/config'
import type { Coordinates, RouteCategory, RouteOption, TripInput } from '@/types/aniRoute'

const props = withDefaults(defineProps<{
  routes: RouteOption[]
  selectedRouteId: string
  trip: TripInput
  currentLocation?: Coordinates | null
  originCoordinates?: Coordinates | null
  destinationCoordinates?: Coordinates | null
  deliveryPointCoordinates?: Array<Coordinates | null>
  active?: boolean
  prototypeRoutes?: boolean
}>(), { currentLocation: null, originCoordinates: null, destinationCoordinates: null, deliveryPointCoordinates: () => [], active: false, prototypeRoutes: false })

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
let routeOverlay: SVGSVGElement | null = null
let routeOverlayFrame: number | undefined

const categoryColors: Record<string, string> = { optimal: '#0b7a54', safer: '#2563eb', fastest: '#e4572e' }
const showPrototypeRoutes = computed(() => props.prototypeRoutes)
const prototypeCategoryOrder: RouteCategory[] = ['optimal', 'safer', 'fastest']
const routeLayerDefinitions = [
  { category: 'optimal' as const, sourceId: 'route-optimal-source', casingId: 'route-optimal-casing', layerId: 'route-optimal', color: '#0b7a54', offset: 0 },
  { category: 'safer' as const, sourceId: 'route-safer-source', casingId: 'route-safer-casing', layerId: 'route-safer', color: '#2563eb', offset: 0 },
  { category: 'fastest' as const, sourceId: 'route-fastest-source', casingId: 'route-fastest-casing', layerId: 'route-fastest', color: '#e4572e', offset: 0 },
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
  if (!showPrototypeRoutes.value) return uniqueRoutes().filter(route => route.source === 'api')

  const routes = uniqueRoutes()
  return prototypeCategoryOrder.map(category => routes.find(route => route.category === category) ?? {
    id: `prototype-${category}`,
    category,
    geometry: presentationRouteGeometry[category],
    source: 'presentation' as const,
  })
}

function routeGeoJson() {
  if (!hasMapSelection.value && !showPrototypeRoutes.value) {
    return { type: 'FeatureCollection' as const, features: [] }
  }

  return {
    type: 'FeatureCollection' as const,
    features: routeLines().map(route => ({
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

function routeGeoJsonFor(category: RouteCategory) {
  const features = routeGeoJson().features.filter(feature => feature.properties.category === category)
  return { type: 'FeatureCollection' as const, features }
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

const prototypeMapView = {
  center: [120.9, 15.3] as MapPoint,
  zoom: 6.2,
  pitch: 34,
  bearing: -8,
}

function removeRouteOverlay() {
  if (routeOverlayFrame !== undefined) {
    window.cancelAnimationFrame(routeOverlayFrame)
    routeOverlayFrame = undefined
  }
  routeOverlay?.remove()
  routeOverlay = null
}

function ensureRouteOverlay(instance: MapInstance) {
  const canvasContainer = instance.getCanvasContainer()
  if (!routeOverlay || routeOverlay.parentElement !== canvasContainer) {
    routeOverlay?.remove()
    routeOverlay = document.createElementNS('http://www.w3.org/2000/svg', 'svg')
    routeOverlay.classList.add('map-route-overlay')
    routeOverlay.setAttribute('aria-hidden', 'true')
    routeOverlay.setAttribute('focusable', 'false')
    routeOverlay.style.pointerEvents = 'none'
    routeOverlay.style.position = 'absolute'
    routeOverlay.style.inset = '0'
    routeOverlay.style.width = '100%'
    routeOverlay.style.height = '100%'
    routeOverlay.style.zIndex = '1'
    canvasContainer.appendChild(routeOverlay)
  }
  return routeOverlay
}

function updateRouteOverlay() {
  routeOverlayFrame = undefined
  const instance = map.value
  if (!instance || !mapReady.value || !showPrototypeRoutes.value) {
    removeRouteOverlay()
    return
  }

  const mapContainer = instance.getContainer()
  const canvasRect = instance.getCanvas().getBoundingClientRect()
  const overlay = ensureRouteOverlay(instance)
  const width = Math.max(Math.round(canvasRect.width || mapContainer.clientWidth), 1)
  const height = Math.max(Math.round(canvasRect.height || mapContainer.clientHeight), 1)
  overlay.setAttribute('viewBox', `0 0 ${width} ${height}`)
  overlay.setAttribute('width', String(width))
  overlay.setAttribute('height', String(height))
  overlay.style.width = `${width}px`
  overlay.style.height = `${height}px`

  const groups = routeLines()
    .sort((left, right) => Number(left.id === props.selectedRouteId) - Number(right.id === props.selectedRouteId))
    .map(route => {
      const isSelected = route.id === props.selectedRouteId
      const pathData = routeCoordinates(route)
        .map((coordinate, index) => {
          const point = instance.project(coordinate)
          return `${index === 0 ? 'M' : 'L'} ${point.x.toFixed(2)} ${point.y.toFixed(2)}`
        })
        .join(' ')
      const group = document.createElementNS('http://www.w3.org/2000/svg', 'g')
      const casing = document.createElementNS('http://www.w3.org/2000/svg', 'path')
      const line = document.createElementNS('http://www.w3.org/2000/svg', 'path')
      casing.setAttribute('d', pathData)
      casing.setAttribute('fill', 'none')
      casing.setAttribute('stroke', '#ffffff')
      casing.setAttribute('stroke-width', isSelected ? '17' : '9')
      casing.setAttribute('stroke-opacity', isSelected ? '1' : '.1')
      casing.setAttribute('stroke-linecap', 'round')
      casing.setAttribute('stroke-linejoin', 'round')
      line.setAttribute('d', pathData)
      line.setAttribute('fill', 'none')
      line.setAttribute('stroke', categoryColors[route.category] ?? '#0b7a54')
      line.setAttribute('stroke-width', isSelected ? '11' : '5')
      line.setAttribute('stroke-opacity', isSelected ? '1' : '.14')
      line.setAttribute('stroke-linecap', 'round')
      line.setAttribute('stroke-linejoin', 'round')
      group.append(casing, line)
      return group
    })
  overlay.replaceChildren(...groups)
}

function scheduleRouteOverlayUpdate() {
  if (routeOverlayFrame !== undefined) return
  routeOverlayFrame = window.requestAnimationFrame(updateRouteOverlay)
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

function shiftRouteCoordinates(coordinates: MapPoint[], target: MapPoint, anchor: MapPoint): MapPoint[] {
  const longitudeDelta = target[0] - anchor[0]
  const latitudeDelta = target[1] - anchor[1]
  return coordinates.map(([longitude, latitude]) => [longitude + longitudeDelta, latitude + latitudeDelta])
}

function routeThroughWaypoints(waypoints: MapPoint[], category: RouteOption['category']): MapPoint[] {
  if (waypoints.length < 2) return waypoints
  const categoryBend = category === 'safer' ? 0.06 : category === 'fastest' ? -0.045 : 0.018
  const path: MapPoint[] = [waypoints[0]!]

  for (let index = 0; index < waypoints.length - 1; index += 1) {
    const start = waypoints[index]!
    const end = waypoints[index + 1]!
    const delta: MapPoint = [end[0] - start[0], end[1] - start[1]]
    const length = Math.hypot(delta[0], delta[1])
    if (length < 0.000001) {
      path.push(end)
      continue
    }
    const midpoint: MapPoint = [(start[0] + end[0]) / 2, (start[1] + end[1]) / 2]
    const normal: MapPoint = [-delta[1] / length, delta[0] / length]
    const bend = categoryBend * (index % 2 === 0 ? 1 : -1)
    path.push([midpoint[0] + normal[0] * length * bend, midpoint[1] + normal[1] * length * bend])
    path.push(end)
  }
  return path
}

function routeCoordinates(route: Pick<RouteOption, 'category' | 'geometry' | 'source'>): MapPoint[] {
  const baseCoordinates = showPrototypeRoutes.value && !hasMapSelection.value
    ? presentationRouteGeometry[route.category].coordinates
    : route.geometry.coordinates
  const coordinates = baseCoordinates.map(([longitude, latitude]) => [longitude, latitude] as MapPoint)
  if (!coordinates.length) return coordinates

  const { origin } = selectedMapPoints()
  const waypoints = selectedWaypoints()
  if (!waypoints.length) return showPrototypeRoutes.value ? coordinates : []

  if (!showPrototypeRoutes.value && route.source !== 'api') return []

  // Presentation routes connect every selected stop in order so
  // points A, B, C and later stops remain visible in the route preview.
  if (waypoints.length > 1) return routeThroughWaypoints(waypoints, route.category)
  const anchor = origin ? coordinates[0]! : coordinates[coordinates.length - 1]!
  return shiftRouteCoordinates(coordinates, waypoints[0]!, anchor)
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

  const boundPoints = (hasMapSelection.value || showPrototypeRoutes.value)
    ? routeLines().flatMap(route => routeCoordinates(route))
    : []
  if (origin) boundPoints.push(origin)
  destinations.forEach(({ coordinate }) => boundPoints.push(coordinate))
  if (props.currentLocation) boundPoints.push([props.currentLocation.longitude, props.currentLocation.latitude])
  if (!boundPoints.length || !shouldFitBounds) {
    scheduleRouteOverlayUpdate()
    return
  }

  const bounds = new LngLatBounds(boundPoints[0], boundPoints[0])
  for (const point of boundPoints) bounds.extend(point)
  if (shouldFitBounds) instance.fitBounds(bounds, { padding: 72, maxZoom: showPrototypeRoutes.value && !hasMapSelection.value ? 7.5 : 14, duration: 250 })
  scheduleRouteOverlayUpdate()
}

function resetToNeutralView(instance: MapInstance) {
  instance.easeTo({ ...philippinesMapView, duration: 250 })
}

function initialMapView() {
  const { origin, deliveries } = selectedMapPoints()
  const currentLocation = pointFromCoordinates(props.currentLocation)
  const anchor = origin ?? deliveries[0]?.coordinate ?? currentLocation
  if (!anchor && showPrototypeRoutes.value) return prototypeMapView
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
    instance.setPaintProperty(routeLayer.casingId, 'line-width', isSelected ? 16 : 8)
    instance.setPaintProperty(routeLayer.casingId, 'line-opacity', isSelected ? 1 : 0.08)
    instance.setPaintProperty(routeLayer.layerId, 'line-width', isSelected ? 10 : 5)
    instance.setPaintProperty(routeLayer.layerId, 'line-opacity', isSelected ? 1 : 0.14)
  }

  try {
    for (const routeLayer of routeLayerDefinitions) {
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
  scheduleRouteOverlayUpdate()
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
  scheduleRouteOverlayUpdate()
  if (!hasMapSelection.value && !props.currentLocation && !showPrototypeRoutes.value) resetToNeutralView(instance)
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
    const syncMapLayers = () => markStyleReady(instance)
    instance.on('style.load', syncMapLayers)
    instance.on('load', syncMapLayers)
    instance.on('move', scheduleRouteOverlayUpdate)
    instance.on('resize', scheduleRouteOverlayUpdate)
    instance.on('zoom', scheduleRouteOverlayUpdate)
    instance.on('rotate', scheduleRouteOverlayUpdate)
    instance.on('pitch', scheduleRouteOverlayUpdate)
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
watch(() => [props.routes, props.selectedRouteId, props.currentLocation, props.trip.origin, props.trip.destination, props.trip.deliveryPoints, props.originCoordinates, props.destinationCoordinates, props.deliveryPointCoordinates, props.prototypeRoutes], () => updateRoutes(), { deep: true })
onBeforeUnmount(() => {
  if (styleFailureTimer) window.clearTimeout(styleFailureTimer)
  removeRouteOverlay()
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
      <div v-if="!unavailable && mapReady && !hasMapSelection && !currentLocation && !showPrototypeRoutes" class="map-empty-state" role="status">
        <MapPin :size="19" aria-hidden="true" />
        <div>
          <strong>Choose pickup and delivery points</strong>
          <span>Search for locations to focus the map.</span>
        </div>
      </div>
    </div>
    <p id="map-drag-hint" class="map-drag-hint"><Move :size="14" aria-hidden="true" /> {{ hasMapSelection ? 'Drag the selected location pins to reposition pickup and delivery points.' : showPrototypeRoutes ? 'The presentation corridor is ready. Select locations to place draggable pins.' : 'Select pickup and delivery points to place draggable pins on the map.' }}</p>
    <div class="map-legend" aria-label="Route color legend">
      <span><i class="legend-line legend-optimal"></i> Recommended route</span>
      <span><i class="legend-line legend-safer"></i> Safer route</span>
      <span><i class="legend-line legend-fastest"></i> Fastest route</span>
    </div>
    <p class="map-attribution map-attribution-links">
      &copy; <a href="https://carto.com/attributions" target="_blank" rel="noreferrer">CARTO</a>
      &middot; &copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">OpenStreetMap contributors</a>
      &middot; {{ showPrototypeRoutes ? 'Routes follow the selected agricultural corridor.' : 'Live road directions are supplied by the backend.' }}
    </p>
  </section>
</template>
