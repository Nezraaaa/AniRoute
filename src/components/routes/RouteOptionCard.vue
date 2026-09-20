<script setup lang="ts">
import { Clock3, CloudRain, MapPin, ShieldCheck, Thermometer, Truck } from '@lucide/vue'
import Badge from '@/components/ui/Badge.vue'
import Button from '@/components/ui/Button.vue'
import Card from '@/components/ui/Card.vue'
import type { RouteCategory, RouteOption } from '@/types/aniRoute'

defineProps<{
  route: RouteOption
  selected: boolean
  crop: string
  loading?: boolean
}>()
const emit = defineEmits<{
  select: [id: string]
  use: [id: string]
}>()

const categoryText: Record<RouteCategory, string> = {
  optimal: 'Optimal · Best balance',
  safer: 'Safer route',
  fastest: 'Fastest route',
}
const riskText = {
  lower: 'Lower known transport concern',
  moderate: 'Some known transport concern',
  higher: 'Higher known transport concern',
}
</script>

<template>
  <Card :class="['route-option', selected ? 'route-option-selected' : '']">
    <button
      type="button"
      class="route-select-button"
      :aria-pressed="selected"
      :aria-label="`Show ${categoryText[route.category]} on the map`"
      @click="emit('select', route.id)"
    >
      <div class="route-topline">
        <div class="route-name-wrap">
          <span :class="['route-category-mark', `mark-${route.category}`]" aria-hidden="true"></span>
          <div>
            <h3>{{ categoryText[route.category] }}</h3>
            <p class="route-short-reason">{{ route.category === 'optimal' ? 'Recommended for this load' : route.category === 'safer' ? 'Lower known road and flood risk' : 'Shortest estimated travel time' }}</p>
          </div>
        </div>
        <Badge v-if="route.recommended" variant="default">Recommended</Badge>
      </div>
      <div v-if="route.categories && route.categories.length > 1" class="category-badges">
        <Badge v-for="category in route.categories" :key="category" variant="secondary">{{ categoryText[category] }}</Badge>
      </div>
      <div class="route-metrics">
        <div><Clock3 :size="18" aria-hidden="true" /><strong>{{ route.travelTimeMinutes }} min</strong><span>estimated</span></div>
        <div><MapPin :size="18" aria-hidden="true" /><strong>{{ route.distanceKm.toFixed(1) }} km</strong><span>distance</span></div>
      </div>
      <div class="route-details-grid">
        <div class="route-detail">
          <Truck :size="16" aria-hidden="true" />
          <div><span class="detail-label">Road</span><strong>{{ route.roadConditionSummary }}</strong></div>
        </div>
        <div class="route-detail">
          <CloudRain :size="16" aria-hidden="true" />
          <div><span class="detail-label">Weather and flood</span><strong>{{ route.weatherFloodSummary }}</strong></div>
        </div>
        <div class="route-detail">
          <Thermometer :size="16" aria-hidden="true" />
          <div><span class="detail-label">Temperature exposure</span><strong>{{ route.temperatureSummary }}</strong></div>
        </div>
        <div class="route-detail route-detail-risk">
          <ShieldCheck :size="16" aria-hidden="true" />
          <div>
            <span class="detail-label">Crop transport risk · {{ crop }}</span>
            <strong>{{ riskText[route.cropRiskLabel] }}</strong>
          </div>
        </div>
      </div>
      <p class="route-explanation">{{ route.explanation }}</p>
      <p v-if="route.source === 'demo'" class="route-demo-note">Sample risk level · not a spoilage or freshness prediction.</p>
    </button>
    <div class="route-actions">
      <Button class="w-full" size="lg" :disabled="loading" @click="emit('use', route.id)">Use this route</Button>
    </div>
  </Card>
</template>
