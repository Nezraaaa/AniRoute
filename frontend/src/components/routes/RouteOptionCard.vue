<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ChevronDown, Clock3, MapPin, ShieldCheck, Truck, X } from '@lucide/vue'
import Badge from '@/components/ui/Badge.vue'
import Button from '@/components/ui/Button.vue'
import Card from '@/components/ui/Card.vue'
import type { RouteCategory, RouteOption } from '@/types/aniRoute'

const props = defineProps<{
  route: RouteOption
  selected: boolean
  crop: string
  loading?: boolean
  /** This option uses the same road as another option (e.g. the recommended road is also the fastest). */
  sameRoadAs?: 'recommended' | 'fastest' | null
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
  optimal: 'Recommended route',
  safer: 'Safest route',
  fastest: 'Fastest route',
  alternative: 'Alternative route',
}
const riskText = {
  lower: 'Lower known transport concern',
  moderate: 'Some known transport concern',
  higher: 'Higher known transport concern',
}

// Categories this road also wins besides its main one (e.g. the recommended road is also the fastest).
const extraWins = computed(() => (props.route.categories ?? [])
  .filter((win): win is 'fastest' | 'safer' => (win === 'fastest' || win === 'safer') && win !== props.route.category))

const shortReason = computed(() => {
  if (props.sameRoadAs) return `Same road as the ${props.sameRoadAs} route`
  if (props.route.category === 'alternative') return `Different road · +${props.route.extraMinutes} min vs fastest`
  return props.route.category === 'optimal' ? 'Best balance of time, distance, crop and road hazards'
    : props.route.category === 'fastest' ? 'Shortest estimated travel time' : 'Fewest curves, stops and confirmed hazards'
})

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
            <span v-if="extraWins.length && !sameRoadAs" class="route-win-chips">
              <span v-for="win in extraWins" :key="win" :class="['route-win-chip', `route-win-chip-${win}`]">{{ win === 'fastest' ? 'Fastest' : 'Safest' }}</span>
            </span>
            <p class="route-short-reason">{{ shortReason }}</p>
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
      <div class="route-card-metrics" aria-label="Route summary">
        <span class="route-card-metric">
          <Clock3 :size="14" aria-hidden="true" />
          <strong>{{ route.travelTimeMinutes }} min</strong>
          <small>time</small>
        </span>
        <span class="route-card-metric">
          <MapPin :size="14" aria-hidden="true" />
          <strong>{{ route.distanceKm.toFixed(1) }} km</strong>
          <small>distance</small>
        </span>
        <span :class="['route-card-metric', `route-card-risk-${route.cropRiskLabel}`]">
          <ShieldCheck :size="14" aria-hidden="true" />
          <strong>{{ route.cropRiskScore ?? '—' }}</strong>
          <small>risk score</small>
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
          <span :class="`risk-factor-${factorSeverity(route.riskFactors.crop)}`" :aria-label="factorLabel('Crop fragility', route.riskFactors.crop)"><strong>{{ route.riskFactors.crop }}</strong> Crop</span>
          <span :class="`risk-factor-${factorSeverity(route.riskFactors.safety)}`" :aria-label="factorLabel('Road safety risk', route.riskFactors.safety)"><strong>{{ route.riskFactors.safety }}</strong> Road</span>
        </div>
        <p class="crop-profile-summary">{{ route.cropProfileSummary }}</p>
        <p v-if="route.explanation" class="route-explanation">{{ route.explanation }}</p>
      </div>
      <div class="route-actions">
        <Button class="w-full" size="lg" :disabled="loading" @click="emit('use', route.id)">Use this route</Button>
      </div>
    </section>
  </Card>
</template>
