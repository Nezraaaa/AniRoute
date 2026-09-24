<script setup lang="ts">
import { ref, watch } from 'vue'
import { ChevronDown, Clock3, CloudRain, MapPin, ShieldCheck, Thermometer, Truck, X } from '@lucide/vue'
import Badge from '@/components/ui/Badge.vue'
import Button from '@/components/ui/Button.vue'
import Card from '@/components/ui/Card.vue'
import type { RouteCategory, RouteOption } from '@/types/aniRoute'

const props = defineProps<{
  route: RouteOption
  selected: boolean
  crop: string
  loading?: boolean
}>()
const emit = defineEmits<{
  select: [id: string]
  use: [id: string]
}>()
const expanded = ref(false)

function toggleRoute(id: string) {
  emit('select', id)
  expanded.value = props.selected ? !expanded.value : true
}

watch(() => props.selected, selected => {
  if (!selected) expanded.value = false
})

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

function factorSeverity(value: number) {
  if (value >= 55) return 'high'
  if (value >= 35) return 'moderate'
  return 'low'
}

function factorLabel(name: string, value: number) {
  return `${name}: ${value} out of 100, ${factorSeverity(value)} severity`
}
</script>

<template>
  <Card :class="['route-option', selected ? 'route-option-selected' : '', expanded ? 'route-option-expanded' : '', route.recommended ? 'route-option-recommended' : '']">
    <button
      type="button"
      class="route-select-button"
      :aria-pressed="selected"
      :aria-expanded="expanded"
      :aria-controls="`route-details-${route.id}`"
      :aria-label="`${expanded ? 'Close' : 'Open'} ${categoryText[route.category]} details and show it on the map`"
      @click="toggleRoute(route.id)"
    >
      <Badge v-if="route.recommended" class="route-recommended-badge" variant="default">Recommended</Badge>
      <div class="route-topline">
        <div class="route-name-wrap">
          <span :class="['route-category-mark', `mark-${route.category}`]" aria-hidden="true"></span>
          <div>
            <h4 class="route-card-title">{{ categoryText[route.category] }}</h4>
            <p class="route-short-reason">{{ route.category === 'optimal' ? 'Best balance for this crop and load' : route.category === 'safer' ? 'Lowest road and flood exposure' : 'Shortest estimated travel time' }}</p>
          </div>
        </div>
        <span class="route-header-actions">
          <ChevronDown
            :size="19"
            aria-hidden="true"
            :class="['route-chevron', expanded ? 'route-chevron-open' : '']"
          />
        </span>
      </div>
    </button>

    <section v-if="expanded" :id="`route-details-${route.id}`" class="route-floating-panel" role="dialog" :aria-label="`${categoryText[route.category]} details`">
      <div class="route-floating-header">
        <div>
          <span class="detail-label">Selected route</span>
          <strong>{{ categoryText[route.category] }}</strong>
        </div>
        <button type="button" class="route-floating-close" aria-label="Close route details" @click="expanded = false">
          <X :size="18" aria-hidden="true" />
        </button>
      </div>
      <div class="route-floating-content">
        <div v-if="route.categories && route.categories.length > 1" class="category-badges">
          <Badge v-for="category in route.categories" :key="category" variant="secondary">{{ categoryText[category] }}</Badge>
        </div>

        <div class="route-metrics">
          <div><Clock3 :size="18" aria-hidden="true" /><strong>{{ route.travelTimeMinutes }} min</strong><span>estimated</span></div>
          <div><MapPin :size="18" aria-hidden="true" /><strong>{{ route.distanceKm.toFixed(1) }} km</strong><span>distance</span></div>
          <div><ShieldCheck :size="18" aria-hidden="true" /><strong>{{ route.cropRiskScore }}/100</strong><span>crop risk score</span></div>
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
              <span class="detail-label">Crop transport risk · {{ crop.trim() || 'your crop' }}</span>
              <strong>{{ riskText[route.cropRiskLabel] }} · {{ route.cropRiskScore }}/100</strong>
            </div>
          </div>
        </div>

        <div class="risk-breakdown" aria-label="Risk score factors">
          <span :class="`risk-factor-${factorSeverity(route.riskFactors.travelTime)}`" :aria-label="factorLabel('Time', route.riskFactors.travelTime)"><strong>{{ route.riskFactors.travelTime }}</strong> Time</span>
          <span :class="`risk-factor-${factorSeverity(route.riskFactors.distance)}`" :aria-label="factorLabel('Distance', route.riskFactors.distance)"><strong>{{ route.riskFactors.distance }}</strong> Distance</span>
          <span :class="`risk-factor-${factorSeverity(route.riskFactors.road)}`" :aria-label="factorLabel('Road', route.riskFactors.road)"><strong>{{ route.riskFactors.road }}</strong> Road</span>
          <span :class="`risk-factor-${factorSeverity(route.riskFactors.floodWeather)}`" :aria-label="factorLabel('Flood', route.riskFactors.floodWeather)"><strong>{{ route.riskFactors.floodWeather }}</strong> Flood</span>
          <span :class="`risk-factor-${factorSeverity(route.riskFactors.temperature)}`" :aria-label="factorLabel('Heat', route.riskFactors.temperature)"><strong>{{ route.riskFactors.temperature }}</strong> Heat</span>
        </div>
        <p class="crop-profile-summary">{{ route.cropProfileSummary }}</p>
        <p class="route-explanation">{{ route.explanation }}</p>
        <p class="route-score-note">Interpretable transport risk score · not a spoilage percentage.</p>
      </div>
      <div class="route-actions">
        <Button class="w-full" size="lg" :disabled="loading" @click="emit('use', route.id)">Use this route</Button>
      </div>
    </section>
  </Card>
</template>
