import type { RouteOption, TripInput } from '@/types/aniRoute'

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
  'Farm pickup point, Tupi',
  'Polomolok farm gate',
  'Tampakan collection point',
]

export const demoDestinations = [
  'Koronadal trading post',
  'General Santos public market',
  'Tupi consolidation center',
]

const demoHazard = {
  id: 'demo-standing-water',
  name: 'Standing water',
  coordinates: { latitude: 6.428, longitude: 124.895 },
  note: 'Sample road note · demo only',
}

const lines = {
  optimal: [
    [124.957, 6.359], [124.942, 6.382], [124.925, 6.406],
    [124.904, 6.431], [124.882, 6.463], [124.858, 6.493], [124.852, 6.503],
  ] as [number, number][],
  safer: [
    [124.957, 6.359], [124.944, 6.378], [124.934, 6.402],
    [124.915, 6.432], [124.892, 6.462], [124.870, 6.486], [124.852, 6.503],
  ] as [number, number][],
  fastest: [
    [124.957, 6.359], [124.939, 6.378], [124.922, 6.405],
    [124.900, 6.431], [124.881, 6.461], [124.862, 6.488], [124.852, 6.503],
  ] as [number, number][],
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
  const vehicleTimeShift = trip.vehicle === 'Pickup' ? -2 : trip.vehicle === 'Medium truck' ? 7 : trip.vehicle === 'Small truck' ? 0 : 3
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
      id: 'optimal', category: 'optimal', geometry: { type: 'LineString', coordinates: lines.optimal },
      travelTimeMinutes: 54 + timeShift, distanceKm: 32.4 + distanceShift, roadConditionSummary: 'Mostly smooth road',
      weatherFloodSummary: 'Some rain exposure · no live forecast', temperatureSummary: 'Mild exposure · sample only', cropRiskScore: 28 + cropShift + loadRiskShift + vehicleRiskShift,
      cropRiskLabel: riskLabel(28 + cropShift + loadRiskShift + vehicleRiskShift), explanation: 'Balances travel time, distance, road condition, sample weather, temperature and crop sensitivity.',
      recommended: true, knownHazards: [], source: 'demo',
    },
    {
      id: 'safer', category: 'safer', geometry: { type: 'LineString', coordinates: lines.safer },
      travelTimeMinutes: 66 + timeShift, distanceKm: 37.8 + distanceShift, roadConditionSummary: 'Fewer known rough sections',
      weatherFloodSummary: 'Lower sample flood exposure', temperatureSummary: 'Lower heat exposure · sample', cropRiskScore: 18 + cropShift + loadRiskShift + vehicleRiskShift,
      cropRiskLabel: riskLabel(18 + cropShift + loadRiskShift + vehicleRiskShift), explanation: 'Takes longer but has lower known road and flood risk in this sample.',
      recommended: false, knownHazards: [], source: 'demo',
    },
    {
      id: 'fastest', category: 'fastest', geometry: { type: 'LineString', coordinates: lines.fastest },
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
