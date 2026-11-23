<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { BarChart3, FlaskConical, Gauge, ImageOff, RefreshCw, Timer, TriangleAlert } from '@lucide/vue'
import Alert from '@/components/ui/Alert.vue'
import Badge from '@/components/ui/Badge.vue'
import Button from '@/components/ui/Button.vue'
import Card from '@/components/ui/Card.vue'
import CardContent from '@/components/ui/CardContent.vue'
import CardDescription from '@/components/ui/CardDescription.vue'
import CardHeader from '@/components/ui/CardHeader.vue'
import CardTitle from '@/components/ui/CardTitle.vue'
import ConfusionMatrix from '@/components/vision/ConfusionMatrix.vue'
import { fetchModelMetrics } from '@/services/vision'
import type { ModelMetrics } from '@/types/aniRoute'

const metrics = ref<ModelMetrics | null>(null)
const loading = ref(true)
const errorMessage = ref('')

async function load() {
  loading.value = true
  errorMessage.value = ''
  try {
    metrics.value = await fetchModelMetrics()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Reports could not be loaded.'
  } finally {
    loading.value = false
  }
}
onMounted(load)

const r = computed(() => metrics.value?.reports ?? {})
const images = computed(() => metrics.value?.images ?? {})
const main = computed(() => r.value.metrics ?? null)
const latency = computed(() => r.value.latency ?? null)
const optimization = computed(() => r.value.optimization ?? null)
const ablation = computed(() => r.value.ablation ?? null)
const robustness = computed(() => r.value.robustness ?? null)
const smoothing = computed(() => r.value.smoothing ?? null)
const dataset = computed(() => r.value.dataset_stats ?? null)
const gallery = computed(() => metrics.value?.errorGallery ?? {})

const pct = (value: number | null | undefined, digits = 1) => value == null ? '–' : `${(value * 100).toFixed(digits)}%`
const num = (value: number | null | undefined, digits = 3) => value == null ? '–' : Number(value).toFixed(digits)
const pretty = (value: string) => value.replace(/_/g, ' ').replace(/^./, char => char.toUpperCase())
const date = (value?: string) => value ? new Date(value).toLocaleString() : ''

const headline = computed(() => {
  const m = main.value
  const systemFps = latency.value?.system?.fps
  return [
    { label: 'mAP@0.5', value: m ? num(m.overall.map50) : 'pending', hint: 'Area under the precision-recall curve, averaged over classes (IoU ≥ 0.5)' },
    { label: 'mAP@0.5:0.95', value: m ? num(m.overall.map50_95) : 'pending', hint: 'Same, averaged over stricter box-overlap thresholds' },
    { label: 'Precision', value: m ? pct(m.overall.precision) : 'pending', hint: 'Of the alerts raised, how many were real hazards' },
    { label: 'Recall', value: m ? pct(m.overall.recall) : 'pending', hint: 'Of the real hazards, how many were found' },
    { label: 'F1', value: m ? num(m.overall.f1) : 'pending', hint: 'Balance of precision and recall at the operating threshold' },
    { label: 'Laptop CPU speed', value: systemFps ? `${systemFps} FPS` : 'pending', hint: latency.value?.system ? `End-to-end, models ${latency.value.system.models}` : 'Run ml/evaluate.py latency' },
  ]
})
const perClass = computed(() => main.value ? Object.entries(main.value.per_class as Record<string, any>) : [])
const trainingRows = computed(() => (optimization.value?.rows ?? []) as any[])
const latencyRows = computed(() => (latency.value?.rows ?? []) as any[])
const galleryKinds: Array<[string, string]> = [['false_positives', 'False alarms'], ['false_negatives', 'Missed hazards'], ['misclassified', 'Wrong hazard type']]
</script>

<template>
  <div class="page-wrap evaluation-page">
    <header class="page-heading">
      <div>
        <Badge variant="secondary" class="section-kicker">Evidence</Badge>
        <h1>Model evaluation</h1>
        <p>Every number on this page is read from <code>ml/reports/</code>, produced by <code>ml/evaluate.py</code> on data the model never trained on.</p>
      </div>
      <Button variant="outline" size="sm" :disabled="loading" @click="load"><RefreshCw :size="15" aria-hidden="true" /> Refresh</Button>
    </header>

    <Alert v-if="errorMessage" variant="warning"><TriangleAlert :size="19" aria-hidden="true" /><div><strong>Reports unavailable</strong><p>{{ errorMessage }} Start the backend to read <code>ml/reports/</code>.</p></div></Alert>

    <Alert v-else-if="metrics && metrics.status === 'pending'" variant="warning" class="eval-pending">
      <FlaskConical :size="19" aria-hidden="true" />
      <div>
        <strong>Accuracy evaluation pending</strong>
        <p>Model A has not been evaluated yet, so no accuracy numbers are shown. After training:</p>
        <pre class="eval-code">python ml/evaluate.py test --data ml/data/aniroute/data.yaml --run-dir ml/runs/&lt;best&gt;
python ml/evaluate.py compare --runs ml/runs/E0 ml/runs/E1 ml/runs/E2 ml/runs/E3 ml/runs/E4
python ml/evaluate.py latency</pre>
      </div>
    </Alert>

    <section class="metric-cards" aria-label="Headline metrics">
      <div v-for="card in headline" :key="card.label" :class="['metric-card', card.value === 'pending' ? 'metric-card-pending' : '']">
        <span>{{ card.label }}</span>
        <strong>{{ card.value }}</strong>
        <small>{{ card.hint }}</small>
      </div>
    </section>
    <p v-if="main" class="eval-source">
      Test split: {{ main.dataset.images }} images, {{ main.dataset.instances }} labelled hazards · operating threshold {{ main.operating_point.confidence }} ({{ main.operating_point.selection }})
      · model {{ main.model.weights }} #{{ main.model.fingerprint }} · evaluated {{ date(main.evaluated_at) }}
    </p>

    <div v-if="main" class="eval-grid">
      <Card>
        <CardHeader><CardTitle>Per-class results</CardTitle><CardDescription>Counts use IoU ≥ 0.5 at the operating threshold.</CardDescription></CardHeader>
        <CardContent class="table-scroll">
          <table class="lab-table">
            <thead><tr><th>Class</th><th>Boxes</th><th>AP50</th><th>AP50-95</th><th>Precision</th><th>Recall</th><th>F1</th><th>TP</th><th>FP</th><th>FN</th></tr></thead>
            <tbody>
              <tr v-for="[name, row] in perClass" :key="name">
                <td>{{ pretty(name) }}</td><td>{{ row.instances }}</td><td>{{ num(row.ap50) }}</td><td>{{ num(row.ap50_95) }}</td>
                <td>{{ pct(row.precision) }}</td><td>{{ pct(row.recall) }}</td><td>{{ num(row.f1) }}</td>
                <td>{{ row.tp }}</td><td>{{ row.fp }}</td><td>{{ row.fn }}</td>
              </tr>
            </tbody>
          </table>
        </CardContent>
      </Card>
      <Card>
        <CardHeader><CardTitle>Confusion matrix</CardTitle><CardDescription>Correct detections sit on the diagonal.</CardDescription></CardHeader>
        <CardContent><ConfusionMatrix :labels="main.confusion_matrix.labels" :matrix="main.confusion_matrix.matrix" /></CardContent>
      </Card>
    </div>

    <div v-if="images['pr_curve.png'] || images['f1_confidence_curve.png'] || images['training_curves.png']" class="figure-grid">
      <figure v-if="images['pr_curve.png']"><img :src="images['pr_curve.png']" alt="Precision-recall curves per class" /><figcaption>Precision-recall curve per class (test split).</figcaption></figure>
      <figure v-if="images['f1_confidence_curve.png']"><img :src="images['f1_confidence_curve.png']" alt="F1 score against confidence threshold" /><figcaption>The operating threshold is the F1 peak, chosen on the validation split.</figcaption></figure>
      <figure v-if="images['training_curves.png']"><img :src="images['training_curves.png']" alt="Training and validation losses and mAP per epoch" /><figcaption>Training curves (loss and validation mAP per epoch).</figcaption></figure>
    </div>

    <Card class="eval-section">
      <CardHeader><div class="eval-section-title"><BarChart3 :size="18" aria-hidden="true" /><CardTitle>Optimisation: baseline → final</CardTitle></div>
        <CardDescription>Each training run is scored on the validation split; the ★ run is deployed. E5 and E6 are inference-time optimisations of that run.</CardDescription></CardHeader>
      <CardContent>
        <div v-if="trainingRows.length" class="table-scroll">
          <table class="lab-table">
            <thead><tr><th>ID</th><th>Experiment</th><th>Change</th><th>mAP@0.5</th><th>mAP@0.5:0.95</th><th>F1</th><th>CPU ms</th><th>FPS</th></tr></thead>
            <tbody>
              <tr v-for="row in trainingRows" :key="row.id" :class="row.id === optimization.selected ? 'row-selected' : ''">
                <td>{{ row.id }}{{ row.id === optimization.selected ? ' ★' : '' }}</td><td>{{ row.title }}</td>
                <td>{{ row.change }}<template v-if="row.kind === 'inference'"> · before: F1 {{ num(row.f1_before) }}<template v-if="row.map50_before != null">, mAP {{ num(row.map50_before) }}</template></template></td>
                <td>{{ num(row.map50) }}</td><td>{{ num(row.map50_95) }}</td><td>{{ num(row.f1) }}</td><td>{{ row.cpu_ms ?? '–' }}</td><td>{{ row.fps ?? '–' }}</td>
              </tr>
            </tbody>
          </table>
          <img v-if="images['optimization_chart.png']" class="eval-figure eval-figure-narrow" :src="images['optimization_chart.png']" alt="mAP and speed per experiment" />
        </div>
        <p v-else class="lab-muted">Pending: run <code>bash ml/run_cpu_pipeline.sh</code> (or <code>python ml/evaluate.py compare --runs ml/runs/E0 ml/runs/E1</code>).</p>
      </CardContent>
    </Card>

    <div class="eval-grid">
      <Card class="eval-section">
        <CardHeader><div class="eval-section-title"><FlaskConical :size="18" aria-hidden="true" /><CardTitle>Preprocessing: before vs after</CardTitle></div>
          <CardDescription>Same model, CLAHE contrast enhancement switched off (app default), automatic, or always on.</CardDescription></CardHeader>
        <CardContent>
          <table v-if="ablation" class="lab-table">
            <thead><tr><th>CLAHE</th><th>mAP@0.5 (all)</th><th>F1 (all)</th><th>mAP@0.5 (dark images)</th><th>Recall (dark)</th></tr></thead>
            <tbody>
              <tr v-for="mode in ['off', 'auto', 'on']" :key="mode">
                <td>{{ mode }}</td><td>{{ num(ablation.modes[mode]?.overall.map50) }}</td><td>{{ num(ablation.modes[mode]?.overall.f1) }}</td>
                <td>{{ num(ablation.modes[mode]?.dark_subset?.map50) }}</td><td>{{ pct(ablation.modes[mode]?.dark_subset?.recall) }}</td>
              </tr>
            </tbody>
          </table>
          <p v-else class="lab-muted">Pending: produced by <code>ml/evaluate.py test</code>.</p>
          <img v-if="images['preprocessing_before_after.png']" class="eval-figure" :src="images['preprocessing_before_after.png']" alt="Original, CLAHE-enhanced and letterboxed model input side by side" />
        </CardContent>
      </Card>
      <Card class="eval-section">
        <CardHeader><div class="eval-section-title"><Gauge :size="18" aria-hidden="true" /><CardTitle>Robustness</CardTitle></div>
          <CardDescription>Accuracy on harder subsets of the test split.</CardDescription></CardHeader>
        <CardContent>
          <table v-if="robustness && Object.keys(robustness.subsets).length" class="lab-table">
            <thead><tr><th>Subset</th><th>Images</th><th>mAP@0.5</th><th>Precision</th><th>Recall</th></tr></thead>
            <tbody><tr v-for="(row, name) in robustness.subsets" :key="name"><td>{{ pretty(String(name)) }}</td><td>{{ row.images }}</td><td>{{ num(row.map50) }}</td><td>{{ pct(row.precision) }}</td><td>{{ pct(row.recall) }}</td></tr></tbody>
          </table>
          <p v-else class="lab-muted">Pending: produced by <code>ml/evaluate.py test</code>. Name files with <code>night</code>, <code>rain</code> or <code>blur</code> to add tagged subsets.</p>
        </CardContent>
      </Card>
    </div>

    <div class="eval-grid">
      <Card class="eval-section">
        <CardHeader><div class="eval-section-title"><Timer :size="18" aria-hidden="true" /><CardTitle>Speed on this laptop</CardTitle></div>
          <CardDescription>{{ latency ? `${latency.machine?.processor ?? 'CPU'} · ${latency.runs} runs · ${date(latency.evaluated_at)}` : 'Inference time per frame.' }}</CardDescription></CardHeader>
        <CardContent>
          <table v-if="latencyRows.length" class="lab-table">
            <thead><tr><th>Model</th><th>Runtime</th><th>Input</th><th>Mean</th><th>p95</th><th>FPS</th></tr></thead>
            <tbody><tr v-for="(row, index) in latencyRows" :key="index"><td>{{ row.model }}</td><td>{{ row.format }}</td><td>{{ row.imgsz }}</td><td>{{ row.mean_ms }} ms</td><td>{{ row.p95_ms }} ms</td><td>{{ row.fps }}</td></tr></tbody>
          </table>
          <p v-else class="lab-muted">Pending: <code>python ml/evaluate.py latency</code>.</p>
          <img v-if="images['speed_chart.png']" class="eval-figure" :src="images['speed_chart.png']" alt="Frames per second by model and runtime" />
        </CardContent>
      </Card>
      <Card class="eval-section">
        <CardHeader><div class="eval-section-title"><Gauge :size="18" aria-hidden="true" /><CardTitle>Alert smoothing</CardTitle></div>
          <CardDescription>Alerts on the recorded drive with vs without 2-of-3 frame voting.</CardDescription></CardHeader>
        <CardContent>
          <p v-if="smoothing" class="eval-stat-line">
            Drive “{{ smoothing.video }}” ({{ smoothing.duration_s }} s): <strong>{{ smoothing.without_smoothing.alerts_per_minute }}</strong> alerts/min without smoothing →
            <strong>{{ smoothing.with_smoothing.alerts_per_minute }}</strong> with {{ smoothing.with_smoothing.min_hits }}-of-{{ smoothing.with_smoothing.window }} voting.
          </p>
          <p v-else class="lab-muted">Smoothing pending: <code>python ml/evaluate.py smoothing --video backend/samples/&lt;drive&gt;.mp4</code>.</p>
        </CardContent>
      </Card>
    </div>

    <Card v-if="main?.error_breakdown || Object.keys(gallery).length" class="eval-section">
      <CardHeader><div class="eval-section-title"><ImageOff :size="18" aria-hidden="true" /><CardTitle>Error analysis</CardTitle></div>
        <CardDescription>Where the model fails. White boxes are ground truth; the yellow frame marks the error.</CardDescription></CardHeader>
      <CardContent>
        <div v-if="main?.error_breakdown" class="eval-grid eval-grid-tight">
          <table class="lab-table">
            <thead><tr><th>Object size</th><th>Objects</th><th>Missed</th><th>Miss rate</th></tr></thead>
            <tbody><tr v-for="(row, size) in main.error_breakdown.miss_rate_by_size" :key="size"><td>{{ size }}</td><td>{{ row.objects }}</td><td>{{ row.missed }}</td><td>{{ pct(row.miss_rate, 0) }}</td></tr></tbody>
          </table>
          <table class="lab-table">
            <thead><tr><th>Lighting</th><th>Objects</th><th>Missed</th><th>Miss rate</th></tr></thead>
            <tbody><tr v-for="(row, light) in main.error_breakdown.miss_rate_by_lighting" :key="light"><td>{{ light }}</td><td>{{ row.objects }}</td><td>{{ row.missed }}</td><td>{{ pct(row.miss_rate, 0) }}</td></tr></tbody>
          </table>
        </div>
        <div v-for="[kind, title] in galleryKinds" :key="kind">
          <template v-if="gallery[kind]?.length">
            <h3 class="gallery-title">{{ title }}</h3>
            <div class="error-gallery">
              <figure v-for="item in gallery[kind]" :key="item.url"><img :src="item.url" :alt="item.caption" /><figcaption>{{ item.caption }}</figcaption></figure>
            </div>
          </template>
        </div>
      </CardContent>
    </Card>

    <Card v-if="dataset || images['dataset_samples.png']" class="eval-section">
      <CardHeader><CardTitle>Dataset</CardTitle><CardDescription>{{ dataset?.split_rule }} · sources: {{ dataset?.sources?.join(', ') }}</CardDescription></CardHeader>
      <CardContent class="figure-grid">
        <table v-if="dataset" class="lab-table">
          <thead><tr><th>Split</th><th>Images</th><th v-for="name in dataset.classes" :key="name">{{ pretty(name) }} boxes</th></tr></thead>
          <tbody><tr v-for="(count, split) in dataset.images_per_split" :key="split"><td>{{ split }}</td><td>{{ count }}</td><td v-for="name in dataset.classes" :key="name">{{ dataset.instances_per_split?.[split]?.[name] ?? 0 }}</td></tr></tbody>
        </table>
        <img v-if="images['dataset_class_distribution.png']" :src="images['dataset_class_distribution.png']" alt="Boxes per class and split" />
        <img v-if="images['dataset_samples.png']" :src="images['dataset_samples.png']" alt="Example labelled training images per class" />
      </CardContent>
    </Card>

    <Card class="eval-section">
      <CardHeader><div class="eval-section-title"><TriangleAlert :size="18" aria-hidden="true" /><CardTitle>Limitations</CardTitle></div></CardHeader>
      <CardContent>
        <ul class="limits-list">
          <li><strong>Training data is from Indian roads.</strong> The RDD2022 India subset is the closest public match, but there is no labelled Philippine test set yet; expect lower accuracy on local farm-to-market roads until local images are added<template v-if="main?.extra_splits?.test_local"> (local test mAP@0.5 {{ num(main.extra_splits.test_local.map50) }})</template>.</li>
          <li><strong>Standing water is not detected automatically.</strong> Public flooded-road data is too small and inconsistent; drivers report it manually.</li>
          <li><strong>Obstructions are out of scope.</strong> People, animals, fallen trees or landslides on the road are not detected; drivers can still report a hazard manually.</li>
          <li><strong>Small or distant potholes and faint cracks are missed most often</strong> — see the size breakdown above when available.</li>
          <li><strong>Night, rain and motion blur reduce recall.</strong> CLAHE contrast enhancement did not help on our data (see the ablation), so it is off by default.</li>
          <li><strong>Modest accuracy.</strong> A nano model trained for 40 epochs on a laptop CPU; many errors are boxes drawn differently from the annotators' boxes. A larger model and more data need a GPU.</li>
          <li><strong>Route-risk weights are heuristics</strong>, not validated postharvest-loss coefficients; field trials are needed before claiming loss reduction.</li>
          <li><strong>Distance to the hazard is not estimated</strong>; hazards are pinned at the vehicle's GPS position when confirmed.</li>
        </ul>
      </CardContent>
    </Card>
  </div>
</template>
