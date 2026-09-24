import type { LineGeometry, RouteCategory, RouteOption, TripInput } from '@/types/aniRoute'

export const demoTrip: TripInput = {
  crop: '',
  quantity: 0,
  cropLoads: [],
  unit: 'kg',
  vehicle: 'Small truck',
  origin: '',
  destination: '',
  deliveryPoints: [],
}

export const demoOrigins = [
  'Baguio farm pickup point',
  'La Trinidad farm gate',
  'Tuba collection point',
]

export const demoDestinations = [
  'Calamba, Laguna trading post',
  'Santa Rosa, Laguna public market',
  'Los Baños, Laguna consolidation center',
]

const demoHazard = {
  id: 'demo-standing-water',
  name: 'Standing water',
  coordinates: { latitude: 14.48, longitude: 121.02 },
  note: 'Sample road note · demo only',
}

/** Three frontend-only alternatives for the Baguio-to-Laguna prototype corridor. */
export const demoRouteGeometry: Record<RouteCategory, LineGeometry> = {
  optimal: {
    type: 'LineString',
    coordinates: [
      [120.596, 16.402], [120.57, 16.17], [120.68, 15.85],
      [120.72, 15.47], [120.86, 15.10], [120.96, 14.72],
      [121.03, 14.48], [121.17, 14.21],
    ],
  },
  safer: {
    type: 'LineString',
    coordinates: [
      [120.596, 16.402], [120.62, 16.18], [120.78, 15.87],
      [120.92, 15.50], [121.02, 15.12], [121.16, 14.76],
      [121.28, 14.40], [121.18, 14.21],
    ],
  },
  fastest: {
    type: 'LineString',
    coordinates: [
      [120.596, 16.402], [120.54, 16.12], [120.60, 15.77],
      [120.72, 15.39], [120.89, 15.02], [121.03, 14.68],
      [121.11, 14.39], [121.17, 14.21],
    ],
  },
}

export function makeDemoRoutes(trip: TripInput, affectedRouteId?: string): RouteOption[] {
  const defaultOrigin = demoTrip.origin.trim().toLowerCase()
  const defaultDestination = demoTrip.destination.trim().toLowerCase()
  const origin = trip.origin.trim().toLowerCase()
  const destination = trip.destination.trim().toLowerCase()
  const locationText = `${origin}|${destination}`
  const isDefaultCorridor = origin === defaultOrigin && destination === defaultDestination
  const locationShift = isDefaultCorridor
    ? 0
    : 1 + [...locationText].reduce((total, char) => total + (char.codePointAt(0) ?? 0), 0) % 6
  const vehicleTimeShift = trip.vehicle === 'Motorcycle' ? -6 : trip.vehicle === 'Pickup' ? -2 : trip.vehicle === 'Medium truck' ? 7 : trip.vehicle === 'Small truck' ? 0 : 3
  const loadDelta = trip.quantity - 250
  let roundedLoadSteps = loadDelta >= 0
    ? Math.floor(loadDelta / 250 + 0.5)
    : Math.ceil(loadDelta / 250 - 0.5)
  if (loadDelta !== 0 && roundedLoadSteps === 0) roundedLoadSteps = loadDelta > 0 ? 1 : -1
  const loadTimeShift = Math.max(-4, Math.min(10, roundedLoadSteps))
  const loadRiskShift = Math.max(0, Math.min(24, roundedLoadSteps * 4))
  const timeShift = vehicleTimeShift + loadTimeShift + locationShift * 2
  const distanceShift = locationShift * 0.6
  const vehicleRiskShift = trip.vehicle === 'Medium truck' ? 4 : 0
  const cropShift = /leafy|lettuce|pechay/i.test(trip.crop) ? 5 : /banana|mango/i.test(trip.crop) ? -2 : 0
  const riskLabel = (score: number) => score >= 60 ? 'higher' : score >= 35 ? 'moderate' : 'lower'
  const routes: RouteOption[] = [
    {
      id: 'optimal', category: 'optimal', geometry: demoRouteGeometry.optimal,
      travelTimeMinutes: 54 + timeShift, distanceKm: 32.4 + distanceShift, roadConditionSummary: 'Mostly smooth road',
      weatherFloodSummary: 'Some rain exposure · no live forecast', temperatureSummary: 'Mild exposure · sample only', cropRiskScore: 28 + cropShift + loadRiskShift + vehicleRiskShift,
      cropRiskLabel: riskLabel(28 + cropShift + loadRiskShift + vehicleRiskShift), explanation: 'Balances travel time, distance, road condition, sample weather, temperature and crop sensitivity.',
      recommended: true, knownHazards: [], source: 'demo',
    },
    {
      id: 'safer', category: 'safer', geometry: demoRouteGeometry.safer,
      travelTimeMinutes: 66 + timeShift, distanceKm: 37.8 + distanceShift, roadConditionSummary: 'Fewer known rough sections',
      weatherFloodSummary: 'Lower sample flood exposure', temperatureSummary: 'Lower heat exposure · sample', cropRiskScore: 18 + cropShift + loadRiskShift + vehicleRiskShift,
      cropRiskLabel: riskLabel(18 + cropShift + loadRiskShift + vehicleRiskShift), explanation: 'Takes longer but has lower known road and flood risk in this sample.',
      recommended: false, knownHazards: [], source: 'demo',
    },
    {
      id: 'fastest', category: 'fastest', geometry: demoRouteGeometry.fastest,
      travelTimeMinutes: 43 + timeShift, distanceKm: 28.7 + distanceShift, roadConditionSummary: 'One rough road section',
      weatherFloodSummary: 'Standing water noted · sample only', temperatureSummary: 'Higher afternoon heat exposure · sample', cropRiskScore: Math.min(95, 63 + cropShift + loadRiskShift + vehicleRiskShift),
      cropRiskLabel: riskLabel(Math.min(95, 63 + cropShift + loadRiskShift + vehicleRiskShift)), explanation: 'Shortest estimated drive time, with a sample standing-water concern.',
      recommended: false, knownHazards: [demoHazard], source: 'demo',
    },
  ]

  if (affectedRouteId) {
    const affected = routes.find(route => route.id === affectedRouteId)
    if (affected) {
      affected.cropRiskScore = Math.min(95, (affected.cropRiskScore ?? 50) + 28)
      affected.cropRiskLabel = affected.cropRiskScore >= 60 ? 'higher' : 'moderate'
      affected.roadConditionSummary = 'New road hazard confirmed · sample update'
      affected.explanation = 'A confirmed sample road note changed this route’s risk information.'
    }
    const recommendationId = affectedRouteId === 'safer' ? 'optimal' : 'safer'
    const recommendation = routes.find(route => route.id === recommendationId)
    if (recommendation) {
      recommendation.recommended = true
      recommendation.explanation = `Recommended after a confirmed sample hazard changed the ${affectedRouteId} route conditions.`
    }
    for (const route of routes) {
      if (route.id !== recommendationId) route.recommended = false
    }
  }

  return routes
}
