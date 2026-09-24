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

function decodeRoadPolyline(encoded: string): [number, number][] {
  const coordinates: [number, number][] = []
  let index = 0
  let latitude = 0
  let longitude = 0

  const nextDelta = () => {
    let byte = 0
    let shift = 0
    let value = 0
    do {
      byte = encoded.charCodeAt(index++) - 63
      value |= (byte & 0x1f) << shift
      shift += 5
    } while (byte >= 0x20)
    return value & 1 ? ~(value >> 1) : value >> 1
  }

  while (index < encoded.length) {
    latitude += nextDelta()
    longitude += nextDelta()
    coordinates.push([longitude / 1e5, latitude / 1e5])
  }
  return coordinates
}

// Simplified road-following paths captured from the OSM road network for the
// presentation corridor. Keeping them local makes the map reliable on stage.
const presentationRoadPolylines: Record<RouteCategory, string> = {
  optimal: "kpbcBk|`_V_Bf@jHvQnAbTvDdBe@zXp\\n[|XbH`KrOoO~t@nFlWrQf]zGfFr~@oC~EbEgOfi@v@rYgH~FMtUkIUqBrDwIkGkF|@p@xLyIfFfQrPwa@p_@~TzH}IfMZ~LmHfPrNn^jCO|AeI~GrA~GcGlQoAWzCyKbA_HpMxRhSK``@dF_TpC]z@t_AbEjDlRVtFhGdQN|UmZdb@yEw[rQqF|KjJbFzZeGaDfIcObEu@nJlVbC~PbJ^uD{FkHjIk@pRl[xAiFuF}VtBcDvPw@jIfGrPcI|NfRpEgBnEqQv\\`DjBvEaEpKpOlBhJpPeLhQ}PfGUzFdc@gBr@bLdEfF_IvHNvEfNlQhf@bIlBtL~MrKpCdMlf@aGnm@aXxD_GbJv@rJoIxc@gKpUqVzGyWpIoLdY}@xb@qK~I~F|RrCdNkQp[cQhkAkL`T\\Jli@zOtGdCpMaB`R~SgD~I{Kn\\_Gn`@mPjRmc@vSgQ|kAaCpeBjHzN{Jzd@seAnNeL|s@oJpfAyXd}@pB|~@_YjqAjBl_AqQjhAgc@toA{{@zg@wWdhCgx@teAoc@x`A{ThqB{TnpBsuArs@kZfeD{t@dgDiKxpBqVtwAu`@v}CsuAxjA_[d{Eu[xzAyWldDiy@|{@aJju@m@jgAdIlaAlU`v@v\\tmBxkAn~Avd@z~@|Jnx@tAhvDaNx`BuUxgCi{@`bAgRhv@aE~yEw@zzA_SjrAqg@|oAw{@v`Bot@ndCazA`j@uO`t@kIn{@PtgAhJj}FduAzv@pLrhApEnfCyBt|@hL~m@tVt~KthGxkAnf@huEn_B`W`\\b`@rwAlRbQb\\jBjwDwq@vXs@`LrJbDgGZ}eClhA}ZvuAuh@zoAyt@pqAycAvfC{iCt`BkiArnA_m@d}CmfAtyA}y@voAchAfhBe~BjuAqqAfdAyr@pwB}fApdAap@rkMypKjuAu{@rr@kj@j{@idAlfAoqBlvAgtBhhCmzFfXoWdcVwmKx]aEpeApD~TsB`qBfAx]~Pll@dPvEmHeE}q@lB_Hl\\cEhNoKh]sCrf@wd@dj@`BzUaJhp@uBrQyNvNFbOsVj[aNhMpC`Una@rAlSaHrOjCtL_AfQpp@hp@dVlQbH~@hrH{cD~iBi}@jlCadA~_MwAtdAb`@~~@|F|_H{q@`aCu`ArmD_tC~jH{vCniJ_}EpEgA`@nCmQ{Pa]_l@wz@or@gB{FrBeAqLa\\",
  safer: "kpbcBk|`_Vkc@`EqQnYgE\\aJhLbO|OKxJsJvLrB`LkDnC`@l]dUrk@qAlX{DMFvEuEi@m@nGqGJgCpJcVdO}K}DaWjk@uSm@gVnI}SfSmAxRcMrNqWpK_BnHgLdAqKvQsk@xg@gPzE{]nX}A_EeH[yUbIsF}CiMbFwKkIo[jF~AtO_MbC_NnM\\|KrLbHvCkBj@jDmTuD}FzF`GnXgArDfLpEzCjJeBrSkOhAoGtEuVg@wPxHyIn\\gHvJHtGwa@`GoLbJiRyAkQvBsMnJfCtD`Vb@`GvD`IlSxB~SwA~LkKpM}VwBw@lFaJxDsCeEyI`k@iExE{F?pBzDqXbMmIFgJrGe@jEoNjHrC`V_A`C}GiA~FxI}EpK}@zRlHyH`PsCeEdFzIhN{N{GmFbLcJzDm@vJeLQdLPl@wJbJ{DvFeLbPrKuIxQrGoDtMhBGpGeQ~SKnMhNnWrQ|I~DtH_Bnn@tYto@t`@m@`T|EdSJnCdJjRH|BmEja@C`XdGr_@g@|Z|CrZzc@r[|ExD`HqCtH~BnNnPtE`fA\\tz@_SbT_M|c@jI`O{DlDoFhYjBxCn_@|ZxN|D`XoQlXcC~Lav@fn@wJ|UxInNjHjAlCrKuDh^vId`@oDjTvZ}@dcAqTxiAiFjZiJ|nBbLhu@_OpmAgNfo@nCpbBcd@~oAcQgBwLtN{CtFz@LxKvUeClrCwjBfpAw_@laAoe@zN_NdbAaXtz@{ArQkJx@ca@z]ym@n@kOkJqu@f~@scBBgPdMqC|Sc~@w{@}dD|RwJrO}w@lgA}ArbBfIxQwKzd@seAnNeL|s@oJpfAyXd}@pB|~@_YjqAjBl_AqQjhAgc@toA{{@js@q]t|Bmr@zvAoj@~_AqQn~AaPhhCscBhfCgr@xqAoSprC}Gv}AgQvjB_f@v}CsuA`u@{Tfx@qLpqBwHhxAwNrgAqSjqCus@ts@}Kd~AiCfl@dEjr@dM`cAl^hbC`xAvu@zVly@rOvaBhHhkDuLxkBaWxgCi{@`bAgRhv@aE~yEw@rqAyO~rAke@pxAcaAv`Bot@ndCazAtmA{Wfj@mBfp@fBjlAzMrsG~zA~vAhHnfCyBhd@xD|f@dMb~LtyGxkAnf@huEn_B`W`\\b`@rwAxV~RvWn@nsDeq@r\\eA`LrJbDgGZ}eClhA}ZvuAuh@zoAyt@pqAycAvfC{iCt`BkiArnA_m@d}CmfAtyA}y@voAchAfhBe~BjuAqqAfdAyr@pwB}fApdAap@rkMypKjuAu{@rr@kj@j{@idAlfAoqBlvAgtBhhCmzFfXoWdcVwmKx]aEpeApD~TsB`qBfAx]~Pll@dPvEmHeE}q@lB_Hl\\cEhNoKh]sCrf@wd@dj@`BzUaJhp@uBrQyNvNFbOsVj[aNhMpC`Una@rAlSaHrOjCtL_AfQpp@hp@dVlQbH~@hrH{cD~iBi}@jlCadA~_MwAtdAb`@~~@|F|_H{q@`aCu`ArmD_tC~jH{vCniJ_}EpEgA`@nCmQ{Pa]_l@wz@or@gB{FrBeAqLa\\",
  fastest: "kpbcBk|`_VzCiMjLuItGPjJtIxHwJzHnA`[sGjHj@nJ{CdPqPpCqQbPhC~UsAlMsLqFdN`IiGxCdCjMoCnEpApD_EzT`QyIu@oDuEa@hFoN|@hi@bM~FaGhKnClB{CkE{M|@yEvOUjQuFfd@ge@xK|BzDcBnCmMhIeHzL~JzJkMbXdUvPHfGwDbEhOlMzJhYcOzTh@~NuSz_@fJfDkAo@rHjLdStJF~TxR`MjDrDvMs@pL~LpFdH~YnIzKxWzSzKe@M|HoJhKdNnHfQr_@z@vNhLdIdKj\\`RdEfL|Y`KtG`Qd@z{@la@rUx{@x_@GbXjt@bE|CvM_@~Ez^lSl\\pFbYuA~ZjV~f@zXzBvk@jl@pe@Hpq@mIdTfAYsDtT{Kz\\mE~rAGdErFxWuA`GbLlHgI`iAwYz~@fB|~@_YjqAjBl_AqQjhAgc@toA{{@zg@wWdhCgx@teAoc@x`A{ThqB{TnpBsuArs@kZfeD{t@dgDiKxpBqVv}Aqc@fdDuxAxdAwVrtE_ZxzAyWldDiy@|{@aJju@m@jgAdIlaAlU`v@v\\tmBxkAn~Avd@z~@|Jnx@tAhvDaNx`BuUxgCi{@`bAgRhv@aE~yEw@rqAyO~rAke@pxAcaAv`Bot@ndCazAhx@oShcAyFr_AtDhy@lKrsG~zA~vAhHnfCyBhd@xDdc@lKzaMl{GxkAnf@huEn_B`W`\\b`@rwAxV~RvWn@nsDeq@r\\eA`LrJbDgGZ}eClhA}ZvuAuh@zoAyt@pqAycAvfC{iCt`BkiArnA_m@d}CmfAtyA}y@voAchAfhBe~BjuAqqAfdAyr@pwB}fApdAap@rkMypKjuAu{@rr@kj@j{@idAlfAoqBlvAgtBhhCmzFfXoWdcVwmKx]aEpeApD~TsB`qBfAx]~Pll@dPvEmHeE}q@lB_Hl\\cEhNoKh]sCrf@wd@dj@`BzUaJhp@uBrQyNvNFbOsVj[aNhMpC`Una@rAlSaHrOjCtL_AfQpp@hp@dVlQbH~@hrH{cD~iBi}@jlCadA~_MwAtdAb`@~~@|F|_H{q@`aCu`ArmD_tC~jH{vCniJ_}EpEgA`@nCmQ{Pa]_l@wz@or@gB{FrBeAqLa\\",
}

const standingWaterHazard = {
  id: 'standing-water-slex-01',
  name: 'Standing water',
  coordinates: { latitude: 14.48, longitude: 121.02 },
  note: 'Standing water reported on this road segment',
}

export const presentationRouteGeometry: Record<RouteCategory, LineGeometry> = {
  optimal: { type: 'LineString', coordinates: decodeRoadPolyline(presentationRoadPolylines.optimal) },
  safer: { type: 'LineString', coordinates: decodeRoadPolyline(presentationRoadPolylines.safer) },
  fastest: { type: 'LineString', coordinates: decodeRoadPolyline(presentationRoadPolylines.fastest) },
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
      id: 'optimal', time: 310, distance: 312.7,
      road: 'Mostly paved; avoids the roughest mountain section',
      weather: 'Moderate rainfall exposure; low flood exposure',
      temperature: 'Moderate afternoon heat exposure',
      factors: { travelTime: 40, distance: 38, road: 18, floodWeather: 22, temperature: 28 },
      explanation: `Best balance for ${profile.label}: avoids the roughest section while keeping travel time below the safer route.`,
    },
    {
      id: 'safer', time: 365, distance: 356.9,
      road: 'Smoothest available road sections',
      weather: 'Lowest flood and standing-water exposure',
      temperature: 'Lower heat exposure through shaded sections',
      factors: { travelTime: 68, distance: 62, road: 8, floodWeather: 10, temperature: 20 },
      explanation: `Lowest road and flood exposure for ${profile.label}, with 55 additional minutes of travel.`,
    },
    {
      id: 'fastest', time: 292, distance: 298.8,
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
