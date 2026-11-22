<script setup lang="ts">
import { ArrowDown, ArrowRight, Camera, Cpu, Layers, Map as MapIcon, ScanSearch, ShieldCheck, Sparkles, Truck, Users } from '@lucide/vue'
import Badge from '@/components/ui/Badge.vue'
import Card from '@/components/ui/Card.vue'
import CardContent from '@/components/ui/CardContent.vue'
import CardHeader from '@/components/ui/CardHeader.vue'
import CardTitle from '@/components/ui/CardTitle.vue'

const pipeline = [
  { icon: Camera, title: 'Capture', text: 'Phone or dashcam frame, uploaded photo or recorded video' },
  { icon: Layers, title: 'Preprocess', text: 'Fix orientation · CLAHE on dark frames · letterbox to 640×640' },
  { icon: Cpu, title: 'Detect (2 models)', text: 'A: fine-tuned YOLO for potholes and cracks · B: pretrained COCO YOLO for obstructions' },
  { icon: ScanSearch, title: 'Filter', text: 'Confidence threshold · driving-corridor rule · hazard must appear in 2 of 3 frames' },
  { icon: ShieldCheck, title: 'Confirm', text: 'Driver confirms by tap or voice; evidence frame and GPS are saved' },
  { icon: MapIcon, title: 'Re-route', text: 'Hazards within 75 m raise the route’s road risk, weighted by crop sensitivity' },
]

const beneficiaries = [
  { title: 'Smallholder farmers', text: 'Fewer bruised and spoiled harvests on the way to market.' },
  { title: 'Haulers and drivers', text: 'Early warning of potholes and obstructions; safer, smoother routes.' },
  { title: 'Cooperatives and traders', text: 'Route choice that weighs crop sensitivity, not just travel time.' },
  { title: 'LGU road maintenance', text: 'Geotagged, photo-verified reports of road damage on farm-to-market roads.' },
]
</script>

<template>
  <div class="page-wrap about-page">
    <header class="page-heading">
      <div>
        <Badge variant="secondary" class="section-kicker">CSST 106 · Final project</Badge>
        <h1>How AniRoute sees the road</h1>
        <p>A real-world perception system for getting perishable harvests to market with less damage.</p>
      </div>
    </header>

    <section class="about-grid">
      <Card>
        <CardHeader><CardTitle>The problem</CardTitle></CardHeader>
        <CardContent class="about-copy">
          <p>
            Fresh produce in the Philippines loses a large share of its value between farm and market. A JICA study estimates
            postharvest losses of <strong>5–48% for fruits and 16–40% for vegetables</strong>, with handling and transport among
            the causes. Farm-to-market roads are often rough, potholed or flooded, and every jolt bruises tomatoes and leafy
            vegetables.
          </p>
          <p>
            Drivers usually discover these hazards only when they reach them, and route planners rank roads by time and distance
            alone. Nobody combines <em>what the road looks like today</em> with <em>how fragile the cargo is</em>.
          </p>
          <p class="about-cite">Sources and caveats: <code>docs/PROBLEM_AND_OBJECTIVES.md</code>.</p>
        </CardContent>
      </Card>
      <Card>
        <CardHeader><CardTitle>Objectives</CardTitle></CardHeader>
        <CardContent>
          <ol class="about-list">
            <li><strong>Detect</strong> potholes, severe road damage and road obstructions in real time from an ordinary phone or dashcam.</li>
            <li><strong>Improve</strong> detection in poor light with preprocessing, and measure that improvement.</li>
            <li><strong>Reduce false alarms</strong> using a driving-corridor rule and multi-frame confirmation.</li>
            <li><strong>Turn detections into decisions</strong>: confirmed hazards re-rank routes by crop-spoilage risk.</li>
            <li><strong>Prove it</strong> with precision, recall, mAP, a confusion matrix and error analysis on unseen images.</li>
          </ol>
        </CardContent>
      </Card>
    </section>

    <Card class="about-section">
      <CardHeader><CardTitle>System overview</CardTitle></CardHeader>
      <CardContent>
        <ol class="flow" aria-label="Detection pipeline">
          <li v-for="(step, index) in pipeline" :key="step.title" class="flow-step">
            <span class="flow-icon"><component :is="step.icon" :size="20" aria-hidden="true" /></span>
            <strong>{{ step.title }}</strong>
            <span>{{ step.text }}</span>
            <ArrowRight v-if="index < pipeline.length - 1" class="flow-arrow flow-arrow-h" :size="18" aria-hidden="true" />
            <ArrowDown v-if="index < pipeline.length - 1" class="flow-arrow flow-arrow-v" :size="18" aria-hidden="true" />
          </li>
        </ol>
        <p class="about-muted">Browser (Vue) → FastAPI → OpenCV preprocessing → Ultralytics YOLO (PyTorch / ONNX / OpenVINO on CPU) → smoothing → hazard store → OSRM route scoring → MapLibre map.</p>
      </CardContent>
    </Card>

    <section class="about-grid">
      <Card>
        <CardHeader><CardTitle>How the detector works</CardTitle></CardHeader>
        <CardContent class="about-copy">
          <p>
            <strong>YOLO</strong> (“You Only Look Once”) is a one-stage object detector. It looks at the whole image once:
            a convolutional <em>backbone</em> extracts edges, textures and shapes; a <em>neck</em> combines features at several
            scales so both large and small objects are seen; a <em>detection head</em> predicts boxes, a class and a
            confidence for each region. <strong>Non-maximum suppression</strong> then keeps the best box where several overlap.
          </p>
          <p>
            <strong>Pretrained + fine-tuned.</strong> Model A starts from YOLO weights already trained on 118,000 everyday
            COCO photos, then learns potholes and cracks from labelled road images (transfer learning). Model B is that same COCO
            model, used without changes, to spot people, animals and vehicles blocking the lane.
          </p>
          <p>
            <strong>Why CLAHE?</strong> Contrast Limited Adaptive Histogram Equalisation brightens dark regions tile by tile while
            limiting noise. It is applied to lightness only, so colours (and the look of water or asphalt) are unchanged.
          </p>
        </CardContent>
      </Card>
      <Card>
        <CardHeader><CardTitle>Who benefits</CardTitle></CardHeader>
        <CardContent>
          <ul class="beneficiaries">
            <li v-for="item in beneficiaries" :key="item.title"><Users :size="16" aria-hidden="true" /><div><strong>{{ item.title }}</strong><span>{{ item.text }}</span></div></li>
          </ul>
        </CardContent>
      </Card>
    </section>

    <section class="about-grid">
      <Card>
        <CardHeader><CardTitle>Real-world use</CardTitle></CardHeader>
        <CardContent class="about-copy">
          <p><Truck :size="16" aria-hidden="true" class="inline-icon" /> A phone on the dashboard of a produce truck runs AniRoute during a delivery. It warns the driver about hazards ahead and, once a hazard is confirmed, re-checks the route.</p>
          <p><MapIcon :size="16" aria-hidden="true" class="inline-icon" /> Confirmed, geotagged hazards build a shared map of farm-to-market road conditions that cooperatives and LGUs can use to plan repairs.</p>
          <p><Sparkles :size="16" aria-hidden="true" class="inline-icon" /> It runs on an ordinary laptop CPU; exporting to ONNX/OpenVINO makes it fast enough for phones and edge devices.</p>
        </CardContent>
      </Card>
      <Card>
        <CardHeader><CardTitle>Limits and privacy</CardTitle></CardHeader>
        <CardContent class="about-copy">
          <p>Trained mostly on public datasets from other countries; standing water is driver-reported only; COCO has no carabao, landslide or fallen-tree class; route-risk weights are heuristics, not validated loss figures. Details are on the Evaluation page.</p>
          <p>Camera frames are analysed in memory and discarded. Only the frame of a hazard the driver confirms is stored, with its GPS position. People and plates may appear in that frame, so confirmed evidence should be stored securely and kept for a limited time.</p>
        </CardContent>
      </Card>
    </section>
  </div>
</template>
