<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { Camera, CameraOff } from '@lucide/vue'

const props = withDefaults(defineProps<{
  stream: MediaStream | null
  active: boolean
  simulatedFinding?: boolean
}>(), { simulatedFinding: false })

const video = ref<HTMLVideoElement | null>(null)
const isReady = ref(false)
const isPortrait = computed(() => true)

async function attachStream(stream: MediaStream | null) {
  await nextTick()
  isReady.value = false
  if (!video.value) return
  video.value.srcObject = stream
  if (stream) {
    try {
      await video.value.play()
      isReady.value = true
    } catch {
      isReady.value = false
    }
  }
}

watch(() => props.stream, stream => void attachStream(stream), { immediate: true, flush: 'post' })
onMounted(() => void attachStream(props.stream))

function captureFrame(maxWidth = 320, quality = 0.38): string | undefined {
  if (!video.value || video.value.readyState < HTMLMediaElement.HAVE_CURRENT_DATA || !video.value.videoWidth) return undefined
  const canvas = document.createElement('canvas')
  const scale = Math.min(1, maxWidth / video.value.videoWidth)
  canvas.width = Math.round(video.value.videoWidth * scale)
  canvas.height = Math.round(video.value.videoHeight * scale)
  const context = canvas.getContext('2d')
  if (!context) return undefined
  context.drawImage(video.value, 0, 0, canvas.width, canvas.height)
  return canvas.toDataURL('image/jpeg', quality)
}

defineExpose({ video, captureFrame })
</script>

<template>
  <div :class="['camera-preview', active ? 'camera-preview-active' : '']" :data-portrait="isPortrait">
    <video v-if="stream" ref="video" autoplay muted playsinline aria-label="Live vehicle camera preview"></video>
    <div v-if="!stream" class="camera-placeholder">
      <CameraOff :size="30" aria-hidden="true" />
      <strong>Camera preview is off</strong>
      <span>Turn on the camera during an active route.</span>
    </div>
    <div v-if="stream && !isReady" class="camera-loading" aria-live="polite">Opening camera…</div>
    <div v-if="simulatedFinding" class="detection-outline" aria-hidden="true"></div>
    <div v-if="stream" class="camera-live-tag"><Camera :size="14" aria-hidden="true" /> Camera preview</div>
    <span v-if="simulatedFinding" class="camera-demo-tag">SIMULATED SAMPLE</span>
  </div>
</template>
