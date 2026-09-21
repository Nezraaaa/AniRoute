<script setup lang="ts">
import { computed } from 'vue'
import { ChevronDown, Package, Truck } from '@lucide/vue'
import Button from '@/components/ui/Button.vue'
import Card from '@/components/ui/Card.vue'
import CardContent from '@/components/ui/CardContent.vue'
import CardDescription from '@/components/ui/CardDescription.vue'
import CardHeader from '@/components/ui/CardHeader.vue'
import CardTitle from '@/components/ui/CardTitle.vue'
import Input from '@/components/ui/Input.vue'
import Label from '@/components/ui/Label.vue'
import LocationSearch from '@/components/delivery/LocationSearch.vue'
import { demoDestinations, demoOrigins } from '@/data/demo'
import type { AppMode, LocationSuggestion, TripInput } from '@/types/aniRoute'

const props = withDefaults(defineProps<{
  trip: TripInput
  errors: Record<string, string>
  loading?: boolean
  mode?: AppMode
}>(), { mode: 'demo' })
const trip = props.trip
const errors = computed(() => props.errors)
const loading = computed(() => props.loading)
const mode = computed(() => props.mode)
const emit = defineEmits<{
  'find-routes': []
  'location-selected': [field: 'origin' | 'destination', index: number, location: LocationSuggestion]
  'location-cleared': [field: 'origin' | 'destination', index: number]
}>()

const maxDynamicEntries = 8
const vehicleChoices = [
  { value: 'Pickup', label: 'Pickup' },
  { value: 'Motorcycle', label: 'Motorcycle / Habal-habal' },
  { value: 'Small truck', label: 'Small truck' },
  { value: 'Medium truck', label: 'Medium truck' },
]

function normalizeCount(value: string) {
  const count = Number(value)
  if (!Number.isFinite(count)) return 0
  return Math.max(0, Math.min(maxDynamicEntries, Math.floor(count)))
}

function syncTripSummary() {
  trip.crop = trip.cropLoads.map(crop => crop.name.trim()).filter(Boolean).join(', ')
  trip.quantity = trip.cropLoads.reduce((total, crop) => total + (Number.isFinite(crop.quantity) ? crop.quantity : 0), 0)
  trip.destination = trip.deliveryPoints.map(point => point.trim()).filter(Boolean).join(', ')
}

function setCropCount(value: string) {
  const count = normalizeCount(value)
  while (trip.cropLoads.length < count) trip.cropLoads.push({ name: '', quantity: 0 })
  if (trip.cropLoads.length > count) trip.cropLoads.splice(count)
  syncTripSummary()
}

function updateCropName(index: number, value: string) {
  const crop = trip.cropLoads[index]
  if (!crop) return
  crop.name = value
  syncTripSummary()
}

function updateCropQuantity(index: number, value: string) {
  const crop = trip.cropLoads[index]
  if (!crop) return
  const quantity = Number(value)
  crop.quantity = value.trim() === '' || !Number.isFinite(quantity) ? 0 : quantity
  syncTripSummary()
}

function setDeliveryPointCount(value: string) {
  const count = normalizeCount(value)
  while (trip.deliveryPoints.length < count) trip.deliveryPoints.push('')
  if (trip.deliveryPoints.length > count) trip.deliveryPoints.splice(count)
  syncTripSummary()
}

function updateDeliveryPoint(index: number, value: string) {
  if (index >= trip.deliveryPoints.length) return
  trip.deliveryPoints[index] = value
  syncTripSummary()
}

function selectLocation(field: 'origin' | 'destination', index: number, location: LocationSuggestion) {
  emit('location-selected', field, index, location)
}

function clearLocation(field: 'origin' | 'destination', index: number) {
  emit('location-cleared', field, index)
}

function submitForm() {
  syncTripSummary()
  emit('find-routes')
}
</script>

<template>
  <Card class="delivery-card">
    <CardHeader>
      <div class="flex items-start gap-3">
        <span class="section-icon"><Package :size="20" aria-hidden="true" /></span>
        <div>
          <CardTitle>Delivery details</CardTitle>
          <CardDescription>Tell us what you are carrying and where it is going.</CardDescription>
        </div>
      </div>
    </CardHeader>
    <CardContent>
      <form class="delivery-form" novalidate @submit.prevent="submitForm">
        <div class="field-grid">
          <div class="field-group field-span-full repeatable-section">
            <div class="repeatable-count-row">
              <div>
                <Label for="crop-count">How many crop types?</Label>
                <p id="crop-help" class="field-hint">Enter a count to add one name and quantity input for each crop.</p>
              </div>
              <Input id="crop-count" :model-value="trip.cropLoads.length || ''" type="number" inputmode="numeric" min="0" :max="maxDynamicEntries" step="1" placeholder="0" :invalid="Boolean(errors.crop)" aria-describedby="crop-help crop-error" @update:model-value="setCropCount" />
            </div>
            <div v-if="trip.cropLoads.length" class="repeatable-list">
              <div v-for="(crop, index) in trip.cropLoads" :key="`crop-row-${index}`" class="repeatable-row">
                <div class="field-group">
                  <Label :for="`crop-${index}`">Crop {{ index + 1 }}</Label>
                  <Input :id="`crop-${index}`" :model-value="crop.name" type="text" maxlength="60" autocomplete="off" placeholder="Enter crop name" required :invalid="Boolean(errors[`crop-${index}`])" :aria-describedby="`crop-${index}-error`" @update:model-value="updateCropName(index, $event)" />
                  <p v-if="errors[`crop-${index}`]" :id="`crop-${index}-error`" class="field-error" role="alert">{{ errors[`crop-${index}`] }}</p>
                </div>
                <div class="field-group">
                  <Label :for="`crop-quantity-${index}`">Quantity</Label>
                  <div class="unit-input">
                    <Input :id="`crop-quantity-${index}`" :model-value="crop.quantity > 0 ? crop.quantity : ''" type="number" inputmode="decimal" min="1" max="100000" step="0.1" placeholder="Amount" required :invalid="Boolean(errors[`crop-quantity-${index}`])" :aria-describedby="`crop-quantity-${index}-error`" @update:model-value="updateCropQuantity(index, $event)" />
                    <span class="unit-suffix">kg</span>
                  </div>
                  <p v-if="errors[`crop-quantity-${index}`]" :id="`crop-quantity-${index}-error`" class="field-error" role="alert">{{ errors[`crop-quantity-${index}`] }}</p>
                </div>
              </div>
            </div>
            <p v-else class="field-hint">No crop rows yet. Add the number of crop types for this delivery.</p>
            <p v-if="errors.crop" id="crop-error" class="field-error" role="alert">{{ errors.crop }}</p>
            <p v-if="errors.quantity" id="quantity-error" class="field-error" role="alert">{{ errors.quantity }}</p>
          </div>

          <div class="field-group">
            <Label for="vehicle">Vehicle</Label>
            <div class="select-with-icon">
              <Truck :size="17" aria-hidden="true" />
              <select id="vehicle" v-model="trip.vehicle" class="field-control field-control-icon" :aria-invalid="Boolean(errors.vehicle)" aria-describedby="vehicle-error">
                <option v-for="vehicle in vehicleChoices" :key="vehicle.value" :value="vehicle.value">{{ vehicle.label }}</option>
              </select>
              <ChevronDown class="select-chevron" :size="17" aria-hidden="true" />
            </div>
            <p v-if="errors.vehicle" id="vehicle-error" class="field-error" role="alert">{{ errors.vehicle }}</p>
          </div>

          <div class="field-group">
            <Label for="origin">Farm or pickup point</Label>
            <LocationSearch
              id="origin"
              v-model="trip.origin"
              :mode="mode"
              :local-suggestions="demoOrigins"
              placeholder="Enter farm or pickup point"
              :invalid="Boolean(errors.origin)"
              described-by="origin-error"
              @select="selectLocation('origin', 0, $event)"
              @clear-selection="clearLocation('origin', 0)"
            />
            <p v-if="errors.origin" id="origin-error" class="field-error" role="alert">{{ errors.origin }}</p>
          </div>

          <div class="field-group field-span-full repeatable-section">
            <div class="repeatable-count-row">
              <div>
                <Label for="destination-count">How many delivery points?</Label>
                <p id="destination-help" class="field-hint">Add one searchable destination for each stop.</p>
              </div>
              <Input id="destination-count" :model-value="trip.deliveryPoints.length || ''" type="number" inputmode="numeric" min="0" :max="maxDynamicEntries" step="1" placeholder="0" :invalid="Boolean(errors.destination)" aria-describedby="destination-help destination-error" @update:model-value="setDeliveryPointCount" />
            </div>
            <div v-if="trip.deliveryPoints.length" class="repeatable-list">
              <div v-for="(point, index) in trip.deliveryPoints" :key="`destination-row-${index}`" class="repeatable-row repeatable-location-row">
                <div class="field-group field-span-full">
                  <Label :for="`destination-${index}`">Delivery point {{ index + 1 }}</Label>
                  <LocationSearch
                    :id="`destination-${index}`"
                    :model-value="point"
                    :mode="mode"
                    :local-suggestions="demoDestinations"
                    icon="search"
                    placeholder="Search delivery point"
                    :invalid="Boolean(errors[`destination-${index}`])"
                    :described-by="`destination-${index}-error`"
                    @update:model-value="updateDeliveryPoint(index, $event)"
                    @select="selectLocation('destination', index, $event)"
                    @clear-selection="clearLocation('destination', index)"
                  />
                  <p v-if="errors[`destination-${index}`]" :id="`destination-${index}-error`" class="field-error" role="alert">{{ errors[`destination-${index}`] }}</p>
                </div>
              </div>
            </div>
            <p v-else class="field-hint">No delivery points yet. Add the number of stops for this trip.</p>
            <p v-if="errors.destination" id="destination-error" class="field-error" role="alert">{{ errors.destination }}</p>
          </div>
        </div>

        <Button type="submit" size="lg" class="w-full" :disabled="loading">
          <span v-if="loading" class="loading-dot" aria-hidden="true"></span>
          {{ loading ? 'Finding routes...' : 'Find routes' }}
        </Button>
      </form>
    </CardContent>
  </Card>
</template>
