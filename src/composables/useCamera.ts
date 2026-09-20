import { computed, onBeforeUnmount, ref } from 'vue'

export function useCamera() {
  const stream = ref<MediaStream | null>(null)
  const status = ref<'inactive' | 'permission-needed' | 'on' | 'denied' | 'unavailable'>('inactive')
  const errorMessage = ref('')
  const isOn = computed(() => status.value === 'on' && stream.value !== null)

  async function start() {
    if (!navigator.mediaDevices?.getUserMedia) {
      status.value = 'unavailable'
      errorMessage.value = 'This browser cannot open the camera. Route guidance is still available.'
      return false
    }
    stop(false)
    status.value = 'permission-needed'
    errorMessage.value = ''
    try {
      stream.value = await navigator.mediaDevices.getUserMedia({
        audio: false,
        video: {
          facingMode: { ideal: 'environment' },
          width: { ideal: 720 },
          height: { ideal: 1280 },
        },
      })
      status.value = 'on'
      return true
    } catch (error) {
      const denied = error instanceof DOMException && (error.name === 'NotAllowedError' || error.name === 'SecurityError')
      status.value = denied ? 'denied' : 'unavailable'
      errorMessage.value = denied
        ? 'Camera permission was not granted. You can continue this trip and try again.'
        : 'The camera could not be opened. You can continue this trip and retry.'
      return false
    }
  }

  function stop(resetStatus = true) {
    stream.value?.getTracks().forEach(track => track.stop())
    stream.value = null
    if (resetStatus) status.value = 'inactive'
  }

  onBeforeUnmount(() => stop())
  return { stream, status, errorMessage, isOn, start, stop }
}
