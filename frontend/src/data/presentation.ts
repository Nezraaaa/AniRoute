import type { LineGeometry, RiskLevel, RouteCategory, RouteOption, TripInput } from '@/types/aniRoute'

export const presentationTrip: TripInput = {
  crop: 'Tomatoes',
  quantity: 250,
  cropLoads: [{ name: 'Tomatoes', quantity: 250 }],
  unit: 'kg',
  vehicle: 'Small truck',
  origin: 'Baguio farm pickup point',
  destination: 'Calamba, Laguna trading post',
  deliveryPoints: ['Calamba, Laguna trading post'],
}

export const presentationOrigins = [
  'Baguio farm pickup point',
  'La Trinidad farm gate',
  'Tuba collection point',
]

export const presentationDestinations = [
  'Calamba, Laguna trading post',
  'Santa Rosa, Laguna public market',
  'Los Baños, Laguna consolidation center',
]

const standingWaterHazard = {
  id: 'standing-water-slex-01',
  name: 'Standing water',
  coordinates: { latitude: 14.48, longitude: 121.02 },
  note: 'Standing water reported on this road segment',
}

export const presentationRouteGeometry: Record<RouteCategory, LineGeometry> = {
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

type CropProfile = {
  label: string
  weights: { travelTime: number; distance: number; road: number; floodWeather: number; temperature: number }
  summary: string
}

const cropProfiles: Array<{ match: RegExp; profile: CropProfile }> = [
  {
    match: /tomato/i,
    profile: {
      label: 'tomatoes',
      weights: { travelTime: 1.25, distance: 0.55, road: 1.5, floodWeather: 1.25, temperature: 1.2 },
      summary: 'Tomatoes are highly sensitive to vibration, delay, standing water and heat exposure.',
    },
  },
  {
    match: /leafy|lettuce|pechay|cabbage/i,
    profile: {
      label: 'leafy vegetables',
      weights: { travelTime: 1.4, distance: 0.4, road: 1.15, floodWeather: 1.25, temperature: 1.55 },
      summary: 'Leafy vegetables prioritize shorter travel time and lower temperature exposure.',
    },
  },
  {
    match: /mango|banana|fruit/i,
    profile: {
      label: 'fruit',
      weights: { travelTime: 1.05, distance: 0.75, road: 1.15, floodWeather: 0.9, temperature: 0.85 },
      summary: 'Fruit routing balances bruising risk, travel time and road condition.',
    },
  },
  {
    match: /rice|corn|maize|grain|onion|potato/i,
    profile: {
      label: 'durable crops',
      weights: { travelTime: 1.3, distance: 1.8, road: 0.25, floodWeather: 0.25, temperature: 0.2 },
      summary: 'Durable crops place more emphasis on travel efficiency and distance.',
    },
  },
]

const tomatoProfile = cropProfiles[0]!.profile

function profileFor(crop: string): CropProfile {
  return cropProfiles.find(item => item.match.test(crop))?.profile ?? tomatoProfile
}

function weightedScore(
  factors: RouteOption['riskFactors'],
  profile: CropProfile,
  adjustment: number,
) {
  const keys = ['travelTime', 'distance', 'road', 'floodWeather', 'temperature'] as const
  const totalWeight = keys.reduce((sum, key) => sum + profile.weights[key], 0)
  const weighted = keys.reduce((sum, key) => sum + factors[key] * profile.weights[key], 0) / totalWeight
  return Math.max(0, Math.min(100, Math.round(weighted + adjustment)))
}

function riskLabel(score: number): RiskLevel {
  return score >= 55 ? 'higher' : score >= 35 ? 'moderate' : 'lower'
}

export function makePresentationRoutes(trip: TripInput, affectedRouteId?: string): RouteOption[] {
  const profile = profileFor(trip.crop)
  const vehicleTimeShift = trip.vehicle === 'Motorcycle' ? -18 : trip.vehicle === 'Pickup' ? -10 : trip.vehicle === 'Medium truck' ? 22 : 0
  const loadSteps = Math.max(0, Math.ceil((trip.quantity - 250) / 250))
  const timeShift = vehicleTimeShift + loadSteps * 5
  const riskAdjustment = loadSteps * 3 + (trip.vehicle === 'Medium truck' ? 3 : 0)

  const specifications: Array<{
    id: RouteCategory
    time: number
    distance: number
    road: string
    weather: string
    temperature: string
    factors: RouteOption['riskFactors']
    explanation: string
  }> = [
    {
      id: 'optimal', time: 310, distance: 253.4,
      road: 'Mostly paved; avoids the roughest mountain section',
      weather: 'Moderate rainfall exposure; low flood exposure',
      temperature: 'Moderate afternoon heat exposure',
      factors: { travelTime: 40, distance: 38, road: 18, floodWeather: 22, temperature: 28 },
      explanation: `Best balance for ${profile.label}: avoids the roughest section while keeping travel time below the safer route.`,
    },
    {
      id: 'safer', time: 328, distance: 269.8,
      road: 'Smoothest available road sections',
      weather: 'Lowest flood and standing-water exposure',
      temperature: 'Lower heat exposure through shaded sections',
      factors: { travelTime: 68, distance: 62, road: 8, floodWeather: 10, temperature: 20 },
      explanation: `Lowest road and flood exposure for ${profile.label}, with 18 additional minutes of travel.`,
    },
    {
      id: 'fastest', time: 292, distance: 241.7,
      road: 'Rough pavement on two road segments',
      weather: 'Standing water reported on the fastest corridor',
      temperature: 'Highest afternoon heat exposure',
      factors: { travelTime: 22, distance: 20, road: 78, floodWeather: 68, temperature: 72 },
      explanation: `18 minutes quicker, but rough pavement, standing water and heat raise transport risk for ${profile.label}.`,
    },
  ]

  const routes: RouteOption[] = specifications.map(specification => {
    const factors = { ...specification.factors }
    if (specification.id === affectedRouteId) factors.road = Math.min(100, factors.road + 38)
    const cropRiskScore = weightedScore(factors, profile, riskAdjustment)
    return {
      id: specification.id,
      category: specification.id,
      geometry: presentationRouteGeometry[specification.id],
      travelTimeMinutes: specification.time + timeShift,
      distanceKm: specification.distance,
      roadConditionSummary: specification.id === affectedRouteId ? 'New road obstruction confirmed on this route' : specification.road,
      weatherFloodSummary: specification.weather,
      temperatureSummary: specification.temperature,
      cropRiskScore,
      cropRiskLabel: riskLabel(cropRiskScore),
      riskFactors: factors,
      cropProfileSummary: profile.summary,
      explanation: specification.id === affectedRouteId
        ? `A confirmed road obstruction increased this route's road-risk contribution.`
        : specification.explanation,
      recommended: false,
      knownHazards: specification.id === 'fastest' ? [standingWaterHazard] : [],
      source: 'presentation',
    }
  })

  const recommendation = routes.reduce((best, route) =>
    (route.cropRiskScore ?? 100) < (best.cropRiskScore ?? 100) ? route : best,
  )
  recommendation.recommended = true
  if (affectedRouteId) {
    recommendation.explanation = `${recommendation.explanation} It now has the lowest crop transport risk score after the road update.`
  }
  return routes
}
