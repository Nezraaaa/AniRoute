<script setup lang="ts">
import { nextTick, onMounted, ref, watch } from 'vue'
import { Camera, CameraOff } from '@lucide/vue'
import DetectionOverlay from '@/components/vision/DetectionOverlay.vue'
import { captureVideoFrame } from '@/lib/frames'
import type { VisionDetection } from '@/types/aniRoute'

const props = withDefaults(defineProps<{
  stream: MediaStream | null
  active: boolean
  /** Recorded road video analysed instead of the live camera. */
  videoSrc?: string | null
  detections?: VisionDetection[]
}>(), { videoSrc: null, detections: () => [] })

const video = ref<HTMLVideoElement | null>(null)
const isReady = ref(false)
const mediaSize = ref({ width: 0, height: 0 })

async function attachSource() {
  await nextTick()
  isReady.value = false
  const element = video.value
  if (!element) return
  if (props.stream) {
    element.srcObject = props.stream
  } else {
    element.srcObject = null
    if (props.videoSrc && element.src !== props.videoSrc) element.src = props.videoSrc
  }
  if (props.stream || props.videoSrc) {
    try {
      await element.play()
      isReady.value = true
    } catch {
      isReady.value = false
    }
  }
}

function onLoaded() {
  if (!video.value) return
  mediaSize.value = { width: video.value.videoWidth, height: video.value.videoHeight }
  isReady.value = true
}

watch(() => [props.stream, props.videoSrc], () => void attachSource(), { immediate: true, flush: 'post' })
onMounted(() => void attachSource())

function captureFrame(maxWidth = 640, quality = 0.7): string | undefined {
  return captureVideoFrame(video.value, maxWidth, quality)
}

defineExpose({ video, captureFrame })
</script>

<template>
  <div :class="['camera-preview', active ? 'camera-preview-active' : '']" data-portrait="true">
    <video
      v-if="stream || videoSrc"
      ref="video"
      autoplay
      muted
      playsinline
      :loop="!stream"
      crossorigin="anonymous"
      :aria-label="stream ? 'Live vehicle camera preview' : 'Recorded road video being analysed'"
      @loadedmetadata="onLoaded"
    ></video>
    <DetectionOverlay
      v-if="(stream || videoSrc) && mediaSize.width && detections.length"
      :detections="detections"
      :media-width="mediaSize.width"
      :media-height="mediaSize.height"
      fit="cover"
      compact
    />
    <div v-if="!stream && !videoSrc" class="camera-placeholder">
      <CameraOff :size="30" aria-hidden="true" />
      <strong>Road camera is off</strong>
      <span>Turn on the camera to start road analysis.</span>
    </div>
    <div v-if="(stream || videoSrc) && !isReady" class="camera-loading" aria-live="polite">Opening video…</div>
    <div v-if="stream || videoSrc" class="camera-live-tag">
      <Camera :size="14" aria-hidden="true" /> {{ stream ? 'Road analysis' : 'Recorded drive' }}
    </div>
  </div>
</template>
