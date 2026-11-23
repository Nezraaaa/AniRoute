<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { Camera, Film, ImageUp, ScanSearch, Upload } from '@lucide/vue'
import Alert from '@/components/ui/Alert.vue'
import Badge from '@/components/ui/Badge.vue'
import Button from '@/components/ui/Button.vue'
import Card from '@/components/ui/Card.vue'
import CardContent from '@/components/ui/CardContent.vue'
import CardDescription from '@/components/ui/CardDescription.vue'
import CardHeader from '@/components/ui/CardHeader.vue'
import CardTitle from '@/components/ui/CardTitle.vue'
import DetectionOverlay from '@/components/vision/DetectionOverlay.vue'
import LiveVideoDetector from '@/components/vision/LiveVideoDetector.vue'
import PreprocessStages from '@/components/vision/PreprocessStages.vue'
import { useCamera } from '@/composables/useCamera'
import { detectImage, fetchModelInfo, fetchSamples, formatConfidence, hazardColors, hazardLabels } from '@/services/vision'
import type { ClaheMode, DetectResult, ModelInfo, SampleMedia } from '@/types/aniRoute'

type Tab = 'image' | 'video' | 'webcam'
interface LabImage { id: string; name: string; url: string; blob?: Blob; remote?: boolean; size?: { width: number; height: number } }

const tab = ref<Tab>('image')
const modelInfo = ref<ModelInfo | null>(null)
const infoError = ref('')
const samples = ref<SampleMedia[]>([])
const images = ref<LabImage[]>([])
const selectedId = ref<string | null>(null)
const result = ref<DetectResult | null>(null)
const detecting = ref(false)
const detectError = ref('')
const conf = ref(0.35)
const clahe = ref<ClaheMode>('off')
const showCorridor = ref(true)
const showAnnotated = ref(false)
const videoSrc = ref<string | null>(null)
const videoName = ref('')
const camera = useCamera()
const imageInput = ref<HTMLInputElement | null>(null)
const videoInput = ref<HTMLInputElement | null>(null)
const objectUrls: string[] = []
let requestToken = 0
let confTimer: number | undefined

const selected = computed(() => images.value.find(item => item.id === selectedId.value) ?? null)
const imageSamples = computed(() => samples.value.filter(item => item.kind === 'image'))
const videoSamples = computed(() => samples.value.filter(item => item.kind === 'video'))
const corridor = computed(() => showCorridor.value && modelInfo.value?.models.B.loaded ? modelInfo.value.corridor : null)
const modelAMissing = computed(() => Boolean(modelInfo.value && !modelInfo.value.models.A.loaded && !modelInfo.value.models.A.available))
const detectionRows = computed(() => result.value?.detections ?? [])

async function loadInfo() {
  try {
    modelInfo.value = await fetchModelInfo()
    infoError.value = ''
    if (modelInfo.value.warmingUp) window.setTimeout(loadInfo, 2_000)
  } catch (error) {
    infoError.value = error instanceof Error ? error.message : 'Detection service unavailable.'
  }
  try {
    samples.value = await fetchSamples()
  } catch {
    samples.value = []
  }
}

function addFiles(files: FileList | null) {
  if (!files?.length) return
  const added: LabImage[] = []
  for (const file of Array.from(files).filter(item => item.type.startsWith('image/')).slice(0, 24)) {
    const url = URL.createObjectURL(file)
    objectUrls.push(url)
    added.push({ id: `${file.name}-${file.lastModified}-${Math.random().toString(36).slice(2, 7)}`, name: file.name, url, blob: file })
  }
  if (!added.length) return
  images.value = [...added, ...images.value].slice(0, 24)
  selectedId.value = added[0]!.id
}

function onDrop(event: DragEvent) {
  event.preventDefault()
  addFiles(event.dataTransfer?.files ?? null)
}

function useSample(sample: SampleMedia) {
  const existing = images.value.find(item => item.url === sample.url)
  if (existing) {
    selectedId.value = existing.id
    return
  }
  const item: LabImage = { id: `sample-${sample.name}`, name: sample.name, url: sample.url, remote: true }
  images.value = [item, ...images.value]
  selectedId.value = item.id
}

async function runDetection() {
  const image = selected.value
  if (!image) return
  const token = ++requestToken
  detecting.value = true
  detectError.value = ''
  try {
    let blob = image.blob
    if (!blob) {
      const response = await fetch(image.url)
      blob = await response.blob()
      image.blob = blob
    }
    const next = await detectImage(blob, image.name, { conf: conf.value, clahe: clahe.value, returnStages: true })
    if (token !== requestToken) return
    result.value = next
    image.size = next.image
  } catch (error) {
    if (token !== requestToken) return
    result.value = null
    detectError.value = error instanceof Error ? error.message : 'Detection failed.'
  } finally {
    if (token === requestToken) detecting.value = false
  }
}

function chooseVideo(files: FileList | null) {
  const file = files?.[0]
  if (!file) return
  const url = URL.createObjectURL(file)
  objectUrls.push(url)
  videoSrc.value = url
  videoName.value = file.name
}

function useVideoSample(sample: SampleMedia) {
  videoSrc.value = sample.url
  videoName.value = sample.name
}

watch(selectedId, () => {
  result.value = null
  void runDetection()
})
watch(clahe, () => void runDetection())
watch(conf, () => {
  if (confTimer) window.clearTimeout(confTimer)
  confTimer = window.setTimeout(() => void runDetection(), 350)
})
watch(tab, next => {
  if (next === 'webcam') void camera.start()
  else camera.stop()
})
watch(modelInfo, info => {
  if (info && conf.value === 0.35) conf.value = Number(info.thresholds.modelAConfidence.toFixed(2))
}, { once: true })

onMounted(loadInfo)
onBeforeUnmount(() => {
  camera.stop()
  objectUrls.forEach(url => URL.revokeObjectURL(url))
})
</script>

<template>
  <div class="page-wrap vision-lab">
    <header class="page-heading">
      <div>
        <Badge variant="secondary" class="section-kicker">Computer vision</Badge>
        <h1>Vision Lab</h1>
        <p>Run the AniRoute road-hazard detector on photos, recorded drives or a live camera.</p>
      </div>
      <div class="lab-model-status" aria-live="polite">
        <template v-if="modelInfo">
          <span :class="['lab-status-dot', modelInfo.models.A.loaded ? 'is-on' : modelInfo.models.A.available ? 'is-wait' : 'is-off']"></span>
          <span><strong>Model A</strong> road surface · {{ modelInfo.models.A.loaded ? `loaded (${modelInfo.models.A.runtimeFormat})` : modelInfo.models.A.available ? 'loading…' : 'not trained yet' }}</span>
          <span :class="['lab-status-dot', modelInfo.models.B.loaded ? 'is-on' : 'is-wait']"></span>
          <span><strong>Model B</strong> obstructions · {{ modelInfo.models.B.loaded ? `loaded (${modelInfo.models.B.runtimeFormat})` : 'loading…' }}</span>
        </template>
        <span v-else-if="infoError" class="lab-status-error">Detection service offline</span>
        <span v-else>Connecting…</span>
      </div>
    </header>

    <Alert v-if="infoError" variant="warning" class="lab-alert">
      <ScanSearch :size="19" aria-hidden="true" />
      <div><strong>The detection service is not reachable</strong><p>Start the backend (<code>scripts/start.ps1</code> or <code>uvicorn backend.main:app</code>) and reload this page. {{ infoError }}</p></div>
    </Alert>
    <Alert v-else-if="modelAMissing" variant="warning" class="lab-alert">
      <ScanSearch :size="19" aria-hidden="true" />
      <div><strong>Road-surface model (A) is not trained yet</strong><p>Only obstruction detection (model B, COCO-pretrained) is active. Train model A with <code>ml/notebooks/train_colab.ipynb</code> and save it as <code>backend/models/aniroute-hazards-v1.pt</code>.</p></div>
    </Alert>

    <div class="lab-tabs" role="tablist" aria-label="Input source">
      <button v-for="item in ([['image', 'Image', ImageUp], ['video', 'Video', Film], ['webcam', 'Webcam', Camera]] as const)" :key="item[0]"
        type="button" role="tab" :aria-selected="tab === item[0]" :class="['lab-tab', tab === item[0] ? 'lab-tab-active' : '']" @click="tab = item[0]">
        <component :is="item[2]" :size="16" aria-hidden="true" /> {{ item[1] }}
      </button>
    </div>

    <div class="lab-controls" aria-label="Detection settings">
      <label class="lab-control">
        <span>Confidence threshold <strong>{{ Math.round(conf * 100) }}%</strong></span>
        <input v-model.number="conf" type="range" min="0.05" max="0.95" step="0.05" />
      </label>
      <div class="lab-control">
        <span>Contrast enhancement (CLAHE)</span>
        <div class="segmented" role="group" aria-label="CLAHE mode">
          <button v-for="mode in (['auto', 'on', 'off'] as const)" :key="mode" type="button"
            :class="['segmented-option', clahe === mode ? 'segmented-option-active' : '']" :aria-pressed="clahe === mode" @click="clahe = mode">
            {{ mode === 'auto' ? 'Auto' : mode === 'on' ? 'On' : 'Off' }}
          </button>
        </div>
      </div>
      <label class="lab-toggle">
        <input v-model="showCorridor" type="checkbox" />
        <span>Show driving corridor (model B rule)</span>
      </label>
    </div>

    <!-- IMAGE -->
    <section v-if="tab === 'image'" class="lab-grid">
      <Card class="lab-input-card">
        <CardHeader>
          <CardTitle>Images</CardTitle>
          <CardDescription>Upload road photos or use a held-out test image.</CardDescription>
        </CardHeader>
        <CardContent class="lab-input-content">
          <button type="button" class="drop-zone" @click="imageInput?.click()" @dragover.prevent @drop="onDrop">
            <Upload :size="22" aria-hidden="true" />
            <strong>Drop images or browse</strong>
            <span>JPEG, PNG or WebP · up to 8 MB each</span>
          </button>
          <input ref="imageInput" class="sr-only" type="file" accept="image/*" multiple @change="addFiles(($event.target as HTMLInputElement).files)" />
          <div v-if="imageSamples.length" class="sample-list">
            <span class="detail-label">Samples</span>
            <button v-for="sample in imageSamples" :key="sample.name" type="button" class="sample-chip" :title="sample.source" @click="useSample(sample)">
              <img :src="sample.url" alt="" crossorigin="anonymous" /> <span>{{ sample.caption || sample.name }}</span>
            </button>
          </div>
          <div v-if="images.length" class="thumb-grid" aria-label="Uploaded images">
            <button v-for="item in images" :key="item.id" type="button" :class="['thumb', item.id === selectedId ? 'thumb-active' : '']" :aria-pressed="item.id === selectedId" @click="selectedId = item.id">
              <img :src="item.url" :alt="item.name" crossorigin="anonymous" />
            </button>
          </div>
        </CardContent>
      </Card>

      <div class="lab-result-column">
        <Card class="lab-result-card">
          <CardHeader>
            <div class="lab-result-heading">
              <div>
                <CardTitle>Detections</CardTitle>
                <CardDescription>{{ selected ? selected.name : 'Choose an image to analyse.' }}</CardDescription>
              </div>
              <div v-if="result" class="lab-chip-row">
                <span class="lab-chip">{{ result.detections.length }} found</span>
                <span class="lab-chip">{{ result.timingsMs.total?.toFixed(0) }} ms total</span>
                <span class="lab-chip">CLAHE {{ result.preprocessing.claheApplied ? 'applied' : 'skipped' }}</span>
                <span v-if="result.roiRejected" class="lab-chip">{{ result.roiRejected }} outside corridor ignored</span>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <div v-if="selected" class="lab-image-stage">
              <img v-if="showAnnotated && result?.annotatedImage" :src="result.annotatedImage" alt="Annotated detection result" />
              <template v-else>
                <img :src="selected.url" :alt="selected.name" crossorigin="anonymous" />
                <DetectionOverlay
                  v-if="result"
                  :detections="result.detections"
                  :media-width="result.image.width"
                  :media-height="result.image.height"
                  :corridor="corridor"
                  fit="contain"
                />
              </template>
              <div v-if="detecting" class="lab-busy">Analysing…</div>
            </div>
            <div v-else class="lab-empty">
              <ScanSearch :size="28" aria-hidden="true" />
              <p>Upload a road photo or pick a sample to see bounding boxes, confidence and preprocessing.</p>
            </div>
            <p v-if="detectError" class="lab-error" role="status">{{ detectError }}</p>
            <label v-if="result?.annotatedImage" class="lab-toggle lab-toggle-inline">
              <input v-model="showAnnotated" type="checkbox" /> <span>Show server-rendered result (as saved as evidence)</span>
            </label>
            <table v-if="detectionRows.length" class="lab-table">
              <thead><tr><th>Hazard</th><th>Confidence</th><th>Model</th><th>Box (px)</th></tr></thead>
              <tbody>
                <tr v-for="item in detectionRows" :key="item.id">
                  <td><i class="hazard-swatch" :style="{ background: hazardColors[item.hazardType] }"></i>{{ item.label }}</td>
                  <td>{{ formatConfidence(item.confidence) }}</td>
                  <td>{{ item.model === 'A' ? 'A · fine-tuned' : 'B · pretrained' }}</td>
                  <td class="mono">{{ item.box.map(value => Math.round(value)).join(', ') }}</td>
                </tr>
              </tbody>
            </table>
            <p v-else-if="result && !detecting" class="lab-muted">No hazards above {{ Math.round(conf * 100) }}% confidence. Lower the threshold to see weaker candidates.</p>
          </CardContent>
        </Card>

        <Card v-if="result?.stages?.length" class="lab-stages-card">
          <CardHeader>
            <CardTitle>Preprocessing, step by step</CardTitle>
            <CardDescription>
              Lightness mean {{ result.preprocessing.luminanceMean }} · contrast {{ result.preprocessing.luminanceStd }}.
              CLAHE is off by default (our ablation showed it lowers accuracy on these road images); Auto applies it only to dark or low-contrast frames.
            </CardDescription>
          </CardHeader>
          <CardContent><PreprocessStages :stages="result.stages" /></CardContent>
        </Card>
      </div>
    </section>

    <!-- VIDEO -->
    <section v-else-if="tab === 'video'" class="lab-grid">
      <Card class="lab-input-card">
        <CardHeader>
          <CardTitle>Recorded drive</CardTitle>
          <CardDescription>Frames are sampled about twice per second while the video plays.</CardDescription>
        </CardHeader>
        <CardContent class="lab-input-content">
          <button type="button" class="drop-zone" @click="videoInput?.click()">
            <Film :size="22" aria-hidden="true" />
            <strong>Choose a video</strong>
            <span>MP4 or WebM dashcam / phone recording</span>
          </button>
          <input ref="videoInput" class="sr-only" type="file" accept="video/*" @change="chooseVideo(($event.target as HTMLInputElement).files)" />
          <div v-if="videoSamples.length" class="sample-list">
            <span class="detail-label">Sample drives</span>
            <button v-for="sample in videoSamples" :key="sample.name" type="button" class="sample-chip" @click="useVideoSample(sample)">
              <Film :size="15" aria-hidden="true" /> <span>{{ sample.caption || sample.name }}</span>
            </button>
          </div>
          <p v-else class="lab-muted">No sample video yet. Add a short road clip to <code>backend/samples/</code> (see docs/DEMO_SCRIPT.md).</p>
        </CardContent>
      </Card>
      <Card class="lab-result-card">
        <CardHeader>
          <CardTitle>Live detections</CardTitle>
          <CardDescription>{{ videoName || 'Choose a video to start.' }}</CardDescription>
        </CardHeader>
        <CardContent>
          <LiveVideoDetector v-if="videoSrc" :src="videoSrc" :conf="conf" :clahe="clahe" :corridor="corridor" />
          <div v-else class="lab-empty"><Film :size="28" aria-hidden="true" /><p>Boxes are drawn over the video as it plays.</p></div>
        </CardContent>
      </Card>
    </section>

    <!-- WEBCAM -->
    <section v-else class="lab-grid lab-grid-single">
      <Card class="lab-result-card">
        <CardHeader>
          <CardTitle>Webcam</CardTitle>
          <CardDescription>Point the camera at a road photo, a printed image or a real road.</CardDescription>
        </CardHeader>
        <CardContent>
          <LiveVideoDetector v-if="camera.stream.value" :stream="camera.stream.value" :conf="conf" :clahe="clahe" :corridor="corridor" />
          <div v-else class="lab-empty">
            <Camera :size="28" aria-hidden="true" />
            <p>{{ camera.errorMessage.value || (camera.status.value === 'permission-needed' ? 'Waiting for camera permission…' : 'Camera is off.') }}</p>
            <Button size="sm" @click="camera.start()">Turn on camera</Button>
          </div>
        </CardContent>
      </Card>
    </section>

    <p class="lab-footnote">
      Supported now: {{ modelInfo?.supportedHazards.map(type => hazardLabels[type]).join(', ') || '—' }}.
      <template v-if="modelInfo?.manualOnlyHazards.length"> Driver-reported only: {{ modelInfo.manualOnlyHazards.map(type => hazardLabels[type].toLowerCase()).join(', ') }}.</template>
      Frames are analysed in memory and are not stored.
    </p>
  </div>
</template>
