import { onBeforeUnmount, ref } from 'vue'
import type { Coordinates } from '@/types/aniRoute'

export function useGeolocation() {
  const coordinates = ref<Coordinates | null>(null)
  const status = ref<'waiting' | 'available' | 'denied' | 'unavailable'>('waiting')
  let watchId: number | null = null

  function start() {
    if (!navigator.geolocation) {
      status.value = 'unavailable'
      return
    }
    status.value = 'waiting'
    watchId = navigator.geolocation.watchPosition(
      position => {
        coordinates.value = {
          latitude: position.coords.latitude,
          longitude: position.coords.longitude,
        }
        status.value = 'available'
      },
      error => {
        status.value = error.code === error.PERMISSION_DENIED ? 'denied' : 'unavailable'
        coordinates.value = null
      },
      { enableHighAccuracy: true, maximumAge: 8_000, timeout: 12_000 },
    )
  }

  function stop() {
    if (watchId !== null && navigator.geolocation) navigator.geolocation.clearWatch(watchId)
    watchId = null
  }

  onBeforeUnmount(stop)
  return { coordinates, status, start, stop }
}
