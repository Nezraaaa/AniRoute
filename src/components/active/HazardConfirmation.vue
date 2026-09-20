<script setup lang="ts">
import { computed } from 'vue'
import { DialogDescription, DialogTitle } from 'reka-ui'
import { CircleAlert, MapPin, Send } from '@lucide/vue'
import Dialog from '@/components/ui/Dialog.vue'
import Button from '@/components/ui/Button.vue'
import Badge from '@/components/ui/Badge.vue'
import type { DetectedHazard, UploadStatus } from '@/types/aniRoute'

const props = defineProps<{
  open: boolean
  hazard: DetectedHazard | null
  detectedFrame: string | null
  uploadStatus: UploadStatus
  uploadMessage: string
  nearbyName: string
}>()
const emit = defineEmits<{
  'update:open': [value: boolean]
  dismiss: []
  confirm: [evidenceFrameDataUrl?: string]
}>()

const hazardNames: Record<string, string> = {
  pothole: 'Pothole',
  severe_road_damage: 'Severe road damage',
  standing_water: 'Standing water',
  road_obstruction: 'Road obstruction',
}
const title = computed(() => props.hazard ? `${hazardNames[props.hazard.type]} detected ahead` : 'Road finding')
const formattedLocation = computed(() => {
  if (!props.hazard?.coordinates) return 'Location could not be pinned.'
  return `${props.hazard.coordinates.latitude.toFixed(5)}, ${props.hazard.coordinates.longitude.toFixed(5)}`
})
const distanceLabel = computed(() => {
  if (props.hazard?.distanceAheadKm === undefined) return 'Distance ahead unavailable'
  return `${Math.round(props.hazard.distanceAheadKm * 1000)} m ahead - sample estimate`
})
const confirmLabel = computed(() => {
  if (props.uploadStatus === 'uploading') return 'Saving...'
  if (props.uploadStatus === 'failed') return 'Retry save'
    return 'Confirm & upload'
})

function confirm() {
  emit('confirm', props.detectedFrame ?? undefined)
}
</script>

<template>
  <Dialog :open="open" @update:open="emit('update:open', $event)">
    <div v-if="hazard" class="hazard-dialog-grid">
      <div class="hazard-preview-column">
        <div class="hazard-detected-frame">
          <img v-if="detectedFrame" :src="detectedFrame" alt="Captured demo camera frame with the detected road finding" />
          <div v-else class="hazard-detected-frame-empty">No captured frame is available for this demo finding.</div>
          <span class="hazard-frame-tag">DETECTED FRAME - DEMO</span>
        </div>
        <p class="camera-evidence-copy">{{ hazard.simulated ? 'This captured frame is demo-only and stays in the browser.' : 'This captured frame is included with the road finding when available.' }}</p>
      </div>
      <div class="hazard-copy-column">
        <Badge variant="warning" class="hazard-detection-badge"><CircleAlert :size="14" aria-hidden="true" /> {{ hazard.simulated ? 'Demo CV detection' : 'Camera finding' }}</Badge>
        <DialogTitle class="hazard-dialog-title">{{ title }}</DialogTitle>
        <DialogDescription class="hazard-dialog-description">Is this a {{ hazardNames[hazard.type].toLowerCase() }}?</DialogDescription>
        <div class="hazard-location-card">
          <p><MapPin :size="17" aria-hidden="true" /> <strong>{{ formattedLocation }}</strong></p>
          <span>{{ distanceLabel }}</span>
          <span>On {{ nearbyName }}</span>
        </div>
        <p class="hazard-confirm-note">{{ hazard.simulated ? 'Confirm to save this simulated computer-vision finding locally, then refresh the demo route.' : 'Confirming saves the road finding and location automatically. It will then check the route again.' }}</p>
        <div v-if="uploadStatus === 'failed'" class="upload-error" role="alert">{{ uploadMessage }}</div>
        <div v-if="uploadStatus === 'uploaded'" class="upload-success" role="status">{{ uploadMessage }}</div>
        <div class="hazard-dialog-actions">
          <Button variant="outline" class="w-full" :disabled="uploadStatus === 'uploading'" @click="emit('dismiss')">Not now</Button>
          <Button class="w-full" :disabled="uploadStatus === 'uploading'" @click="confirm">
            <Send v-if="uploadStatus !== 'uploading'" :size="16" aria-hidden="true" />
            <span v-else class="loading-dot" aria-hidden="true"></span>
            {{ confirmLabel }}
          </Button>
        </div>
      </div>
    </div>
  </Dialog>
</template>
