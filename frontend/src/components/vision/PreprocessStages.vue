<script setup lang="ts">
import { Check, Minus } from '@lucide/vue'
import type { PreprocessStage } from '@/types/aniRoute'

defineProps<{ stages: PreprocessStage[] }>()

const titles: Record<string, string> = {
  original: '1 · Original',
  clahe: '2 · Contrast (CLAHE)',
  denoise: '3 · Denoise',
  letterbox: 'Model input',
}
</script>

<template>
  <ol class="stage-strip" aria-label="Preprocessing stages">
    <li v-for="stage in stages" :key="stage.name" :class="['stage-card', stage.applied ? '' : 'stage-skipped']">
      <div class="stage-image">
        <img v-if="stage.image" :src="stage.image" :alt="`${titles[stage.name] ?? stage.name} preview`" />
      </div>
      <div class="stage-copy">
        <strong>
          <Check v-if="stage.applied" :size="14" aria-hidden="true" />
          <Minus v-else :size="14" aria-hidden="true" />
          {{ titles[stage.name] ?? stage.name }}
        </strong>
        <span>{{ stage.description }}</span>
        <small>{{ stage.ms.toFixed(1) }} ms</small>
      </div>
    </li>
  </ol>
</template>
