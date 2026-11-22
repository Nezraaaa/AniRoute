<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { Pause, Play } from '@lucide/vue'
import DetectionOverlay from './DetectionOverlay.vue'
import Button from '@/components/ui/Button.vue'
import { useFrameScanner } from '@/composables/useFrameScanner'
import { detectFrame, hazardColors, hazardLabels } from '@/services/vision'
import type { ClaheMode, CorridorSettings, HazardType, VisionDetection } from '@/types/aniRoute'

const props = withDefaults(defineProps<{
  src?: string | null
  stream?: MediaStream | null
  conf?: number | null
  clahe?: ClaheMode
  corridor?: CorridorSettings | null
  intervalMs?: number
}>(), { src: null, stream: null, conf: null, clahe: 'auto', corridor: null, intervalMs: 500 })

const video = ref<HTMLVideoElement | null>(null)
const detections = ref<VisionDetection[]>([])
const mediaSize = ref({ width: 0, height: 0 })
const playing = ref(false)
const counts = ref<Record<HazardType, number>>({ pothole: 0, severe_road_damage: 0, standing_water: 0, road_obstruction: 0 })
const timeline = ref<Array<{ t: number; types: HazardType[] }>>([])
const errorMessage = ref('')

const scanner = useFrameScanner({
  getVideo: () => video.value,
  intervalMs: props.intervalMs,
  send: frame => detectFrame(frame, { conf: props.conf, clahe: props.clahe }),
  onResult: result => {
    detections.value = result.detections
    const types = [...new Set(result.detections.map(item => item.hazardType))]
    for (const type of types) counts.value[type] += 1
    if (types.length && video.value) {
      timeline.value = [...timeline.value.slice(-79), { t: video.value.currentTime, types }]
    }
  },
  onError: error => {
    errorMessage.value = error instanceof Error ? error.message : 'Detection failed.'
  },
})

const duration = computed(() => video.value?.duration && Number.isFinite(video.value.duration) ? video.value.duration : null)

function reset() {
  detections.value = []
  timeline.value = []
  counts.value = { pothole: 0, severe_road_damage: 0, standing_water: 0, road_obstruction: 0 }
  errorMessage.value = ''
}

async function attach() {
  await nextTick()
  const element = video.value
  if (!element) return
  reset()
  if (props.stream) {
    element.srcObject = props.stream
  } else {
    element.srcObject = null
    if (props.src) element.src = props.src
  }
  try {
    await element.play()
  } catch {
    // Autoplay may be blocked until the user presses play.
  }
}

function onLoaded() {
  if (!video.value) return
  mediaSize.value = { width: video.value.videoWidth, height: video.value.videoHeight }
}

function onPlay() {
  playing.value = true
  scanner.start()
}

function onPause() {
  playing.value = false
  scanner.stop()
}

async function togglePlay() {
  if (!video.value) return
  if (video.value.paused) await video.value.play().catch(() => undefined)
  else video.value.pause()
}

watch(() => [props.src, props.stream], attach, { immediate: true })
watch(() => [props.conf, props.clahe], () => { detections.value = [] })
onBeforeUnmount(() => scanner.stop())

defineExpose({ reset })
</script>

<template>
  <div class="live-detector">
    <div class="live-detector-stage">
      <video
        ref="video"
        class="live-detector-video"
        crossorigin="anonymous"
        playsinline
        muted
        :loop="!stream"
        :controls="!stream"
        @loadedmetadata="onLoaded"
        @play="onPlay"
        @playing="onPlay"
        @pause="onPause"
        @ended="onPause"
      ></video>
      <DetectionOverlay
        v-if="mediaSize.width"
        :detections="detections"
        :media-width="mediaSize.width"
        :media-height="mediaSize.height"
        :corridor="corridor"
        fit="contain"
      />
      <div class="live-detector-badges">
        <span class="lab-chip lab-chip-dark">{{ scanner.fps.value ? `${scanner.fps.value} analysed fps` : playing ? 'Starting…' : 'Paused' }}</span>
        <span v-if="scanner.latencyMs.value" class="lab-chip lab-chip-dark">{{ scanner.latencyMs.value }} ms round trip</span>
      </div>
    </div>
    <div class="live-detector-controls">
      <Button v-if="!stream" size="sm" variant="outline" @click="togglePlay">
        <Pause v-if="playing" :size="15" aria-hidden="true" /><Play v-else :size="15" aria-hidden="true" />
        {{ playing ? 'Pause' : 'Play' }}
      </Button>
      <div class="hazard-counts" aria-label="Frames with each hazard">
        <span v-for="(count, type) in counts" :key="type" class="hazard-count">
          <i :style="{ background: hazardColors[type] }"></i>{{ hazardLabels[type] }} <strong>{{ count }}</strong>
        </span>
      </div>
    </div>
    <div v-if="duration && timeline.length" class="detection-timeline" aria-label="Detections along the video">
      <span
        v-for="(event, index) in timeline"
        :key="index"
        class="timeline-mark"
        :style="{ left: `${(event.t / duration) * 100}%`, background: hazardColors[event.types[0]!] }"
        :title="`${event.t.toFixed(1)} s · ${event.types.map(type => hazardLabels[type]).join(', ')}`"
      ></span>
    </div>
    <p v-if="errorMessage" class="lab-error" role="status">{{ errorMessage }}</p>
  </div>
</template>
