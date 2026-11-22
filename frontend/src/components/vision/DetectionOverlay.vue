<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { projectBox, type MediaFit } from '@/lib/frames'
import { formatConfidence, hazardColors } from '@/services/vision'
import type { CorridorSettings, VisionDetection } from '@/types/aniRoute'

const props = withDefaults(defineProps<{
  detections: VisionDetection[]
  mediaWidth: number
  mediaHeight: number
  fit?: MediaFit
  corridor?: CorridorSettings | null
  compact?: boolean
}>(), { fit: 'contain', corridor: null, compact: false })

const root = ref<HTMLDivElement | null>(null)
const size = ref({ width: 0, height: 0 })
let observer: ResizeObserver | undefined

function measure() {
  if (!root.value) return
  size.value = { width: root.value.clientWidth, height: root.value.clientHeight }
}

onMounted(() => {
  measure()
  if (typeof ResizeObserver !== 'undefined' && root.value) {
    observer = new ResizeObserver(measure)
    observer.observe(root.value)
  }
})
onBeforeUnmount(() => observer?.disconnect())

const media = computed(() => ({ width: props.mediaWidth, height: props.mediaHeight }))
const boxes = computed(() => props.detections.map(item => ({
  item,
  rect: projectBox(item.boxNorm, size.value, media.value, props.fit),
  color: hazardColors[item.hazardType] ?? '#ffffff',
})))

// Driving corridor (where model B obstructions count), drawn in media coordinates.
const corridorPoints = computed(() => {
  const c = props.corridor
  if (!c) return ''
  const corners: Array<[number, number]> = [
    [0.5 - c.topHalfWidth, c.top], [0.5 + c.topHalfWidth, c.top],
    [0.5 + c.bottomHalfWidth, 1], [0.5 - c.bottomHalfWidth, 1],
  ]
  return corners.map(([x, y]) => {
    const rect = projectBox([x, y, x, y], size.value, media.value, props.fit)
    return `${rect.left.toFixed(1)},${rect.top.toFixed(1)}`
  }).join(' ')
})
</script>

<template>
  <div ref="root" class="detection-overlay" aria-hidden="false">
    <svg v-if="corridor && size.width" class="detection-corridor" :viewBox="`0 0 ${size.width} ${size.height}`" aria-hidden="true">
      <polygon :points="corridorPoints" />
    </svg>
    <div
      v-for="{ item, rect, color } in boxes"
      :key="item.id"
      class="detection-box"
      :data-hazard="item.hazardType"
      :style="{ left: `${rect.left}px`, top: `${rect.top}px`, width: `${rect.width}px`, height: `${rect.height}px`, borderColor: color }"
      role="img"
      :aria-label="`${item.label}, ${formatConfidence(item.confidence)} confidence`"
    >
      <span class="detection-tag" :style="{ background: color }">
        {{ compact ? item.label.replace('Road obstruction', 'Obstruction') : item.label }} {{ formatConfidence(item.confidence) }}
      </span>
    </div>
  </div>
</template>
