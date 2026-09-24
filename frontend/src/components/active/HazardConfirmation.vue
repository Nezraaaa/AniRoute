<script setup lang="ts">
import { computed, watch } from 'vue'
import { DialogDescription, DialogTitle } from 'reka-ui'
import { CircleAlert, MapPin, Send } from '@lucide/vue'
import Dialog from '@/components/ui/Dialog.vue'
import Button from '@/components/ui/Button.vue'
import Badge from '@/components/ui/Badge.vue'
import { useVoiceRecognition, type VoiceCommand } from '@/composables/useVoiceRecognition'
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
  return `${Math.round(props.hazard.distanceAheadKm * 1000)} m ahead`
})
const confirmLabel = computed(() => {
  if (props.uploadStatus === 'uploading') return 'Saving...'
  if (props.uploadStatus === 'failed') return 'Retry save'
    return 'Confirm & upload'
})

function confirm() {
  emit('confirm', props.detectedFrame ?? undefined)
}

function handleVoiceCommand(command: VoiceCommand) {
  if (props.uploadStatus === 'uploading') return
  if (command === 'confirm') confirm()
  else emit('dismiss')
}

const voice = useVoiceRecognition(handleVoiceCommand)
const voiceStatus = computed(() => {
  if (!voice.isSupported.value) return 'Voice commands are unavailable in this browser. You can still confirm with the buttons.'
  if (voice.isListening.value) return 'Listening… say “confirm” to save or “not now” to dismiss.'
  if (voice.errorMessage.value) return voice.errorMessage.value
  if (voice.transcript.value) return `Heard “${voice.transcript.value}”.`
  return 'Say “confirm” to save or “not now” to dismiss.'
})
const voiceFallbackMessage = computed(() => {
  if (voice.isSupported.value && !voice.errorMessage.value) return ''
  return voice.errorMessage.value || 'Automatic voice recognition is unavailable in this browser. Use the buttons below to confirm manually.'
})

watch(() => props.open, open => {
  if (open) {
    voice.reset()
    voice.start()
  }
  else voice.stop()
}, { immediate: true })
watch(() => props.uploadStatus, status => {
  if (status === 'uploading') voice.stop()
})
</script>

<template>
  <Dialog :open="open" @update:open="emit('update:open', $event)">
    <div v-if="hazard" class="hazard-dialog-grid">
      <div class="hazard-preview-column">
        <div class="hazard-detected-frame">
          <img v-if="detectedFrame" :src="detectedFrame" alt="Captured camera frame with the detected road finding" />
          <div v-else class="hazard-detected-frame-empty">Road observation frame ready for confirmation.</div>
          <span class="hazard-frame-tag">ROAD ANALYSIS FRAME</span>
        </div>
        <p class="camera-evidence-copy">{{ hazard.coordinates ? 'The confirmed frame and GPS position are attached to the road observation.' : 'The confirmed frame is attached to the road observation; GPS was unavailable.' }}</p>
      </div>
      <div class="hazard-copy-column">
        <Badge variant="warning" class="hazard-detection-badge"><CircleAlert :size="14" aria-hidden="true" /> Computer vision finding</Badge>
        <DialogTitle class="hazard-dialog-title">{{ title }}</DialogTitle>
        <DialogDescription class="hazard-dialog-description">Is this a {{ hazardNames[hazard.type].toLowerCase() }}?</DialogDescription>
        <div class="hazard-location-card">
          <p><MapPin :size="17" aria-hidden="true" /> <strong>{{ formattedLocation }}</strong></p>
          <span>{{ distanceLabel }}</span>
          <span>On {{ nearbyName }}</span>
        </div>
        <p class="hazard-confirm-note">Confirming adds this finding to the affected road segment and recalculates the recommended route.</p>
        <div v-if="uploadStatus === 'failed'" class="upload-error" role="alert">{{ uploadMessage }}</div>
        <div v-if="uploadStatus === 'uploaded'" class="upload-success" role="status">{{ uploadMessage }}</div>
        <span class="voice-status-live" aria-live="polite">{{ voiceStatus }}</span>
        <p v-if="voiceFallbackMessage" class="voice-fallback-note" role="status">{{ voiceFallbackMessage }}</p>
        <div class="hazard-dialog-actions">
          <Button data-testid="hazard-dismiss-button" variant="outline" class="w-full" :disabled="uploadStatus === 'uploading'" @click="emit('dismiss')">Not now</Button>
          <Button data-testid="hazard-confirm-button" class="w-full" :disabled="uploadStatus === 'uploading'" @click="confirm">
            <Send v-if="uploadStatus !== 'uploading'" :size="16" aria-hidden="true" />
            <span v-else class="loading-dot" aria-hidden="true"></span>
            {{ confirmLabel }}
          </Button>
        </div>
      </div>
    </div>
  </Dialog>
</template>
