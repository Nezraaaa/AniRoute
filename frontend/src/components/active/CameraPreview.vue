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
/** The browser blocked automatic playback (phones do this when no tap started it): ask for one tap. */
const needsTap = ref(false)

// Phones only autoplay video that is muted and inline. Set these as properties (not just attributes) so
// iOS Safari and Android Chrome play the live camera full-size straight away, without a tap.
function prepareForAutoplay(element: HTMLVideoElement) {
  element.muted = true
  element.defaultMuted = true
  element.playsInline = true
  element.setAttribute('playsinline', '')
  element.setAttribute('webkit-playsinline', '')
}

async function tryPlay() {
  const element = video.value
  if (!element || !(props.stream || props.videoSrc)) return
  try {
    await element.play()
    needsTap.value = false
    isReady.value = true
  } catch {
    needsTap.value = true
  }
}

async function attachSource() {
  await nextTick()
  isReady.value = false
  needsTap.value = false
  const element = video.value
  if (!element) return
  prepareForAutoplay(element)
  if (props.stream) {
    element.srcObject = props.stream
  } else {
    element.srcObject = null
    if (props.videoSrc && element.src !== props.videoSrc) element.src = props.videoSrc
  }
  await tryPlay()
}

function updateSize() {
  if (!video.value) return
  mediaSize.value = { width: video.value.videoWidth, height: video.value.videoHeight }
}

function onLoaded() {
  updateSize()
  // Retry once the camera has produced its first frame (some phones reject play() until then).
  if (video.value?.paused) void tryPlay()
  else isReady.value = true
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
      @resize="updateSize"
      @playing="needsTap = false; isReady = true"
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
    <button v-if="(stream || videoSrc) && needsTap" type="button" class="camera-tap-start" @click="tryPlay">
      <Camera :size="22" aria-hidden="true" />
      <span>Tap to start the camera</span>
    </button>
    <div v-else-if="(stream || videoSrc) && !isReady" class="camera-loading" aria-live="polite">Opening video…</div>
    <div v-if="stream || videoSrc" class="camera-live-tag">
      <Camera :size="14" aria-hidden="true" /> {{ stream ? 'Road analysis' : 'Recorded drive' }}
    </div>
  </div>
</template>
