import { onBeforeUnmount, ref } from 'vue'
import type { Coordinates } from '@/types/aniRoute'

export type LocationStatus = 'waiting' | 'available' | 'denied' | 'unavailable' | 'insecure'

/**
 * Live device position for the trip.
 *
 * - A precise (GPS) fix is requested first; if it times out or the device has no GPS, a coarser network
 *   position is requested instead, so laptops and indoor phones still get pinned where possible.
 * - A failed reading never erases a position we already have; only a permission refusal clears it.
 * - Browsers share location only on secure pages (https or localhost); that case is reported as 'insecure'.
 */
export function useGeolocation() {
  const coordinates = ref<Coordinates | null>(null)
  const status = ref<LocationStatus>('waiting')
  const accuracyM = ref<number | null>(null)
  let watchId: number | null = null
  let fallbackStarted = false
  let fallbackDone = false

  function onPosition(position: GeolocationPosition) {
    coordinates.value = { latitude: position.coords.latitude, longitude: position.coords.longitude }
    accuracyM.value = Number.isFinite(position.coords.accuracy) ? Math.round(position.coords.accuracy) : null
    status.value = 'available'
  }

  function onError(error: GeolocationPositionError) {
    if (error.code === error.PERMISSION_DENIED) {
      coordinates.value = null
      status.value = 'denied'
      stop()
      return
    }
    // Timeout or no fix: keep any earlier position, and fall back to a coarse network position once.
    if (coordinates.value) return
    if (!fallbackStarted) {
      fallbackStarted = true
      navigator.geolocation.getCurrentPosition(onPosition, fallbackError => {
        fallbackDone = true
        if (fallbackError.code === fallbackError.PERMISSION_DENIED) onError(fallbackError)
        else if (!coordinates.value) status.value = 'unavailable'
      }, { enableHighAccuracy: false, maximumAge: 60_000, timeout: 20_000 })
    } else if (fallbackDone) {
      status.value = 'unavailable'
    }
  }

  function start() {
    stop()
    fallbackStarted = false
    fallbackDone = false
    if (typeof window !== 'undefined' && window.isSecureContext === false) {
      status.value = 'insecure'
      return
    }
    if (!navigator.geolocation) {
      status.value = 'unavailable'
      return
    }
    if (!coordinates.value) status.value = 'waiting'
    watchId = navigator.geolocation.watchPosition(onPosition, onError,
      { enableHighAccuracy: true, maximumAge: 8_000, timeout: 15_000 })
  }

  function stop() {
    if (watchId !== null && navigator.geolocation) navigator.geolocation.clearWatch(watchId)
    watchId = null
  }

  /** Ask again, e.g. after the user allowed location in the browser's site settings. */
  function retry() {
    start()
  }

  onBeforeUnmount(stop)
  return { coordinates, status, accuracyM, start, stop, retry }
}
