<script setup lang="ts">
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
import type { LocationSuggestion, TripInput } from '@/types/aniRoute'

defineProps<{
  trip: TripInput
  errors: Record<string, string>
  loading?: boolean
}>()
const emit = defineEmits<{
  'find-routes': []
  'location-selected': [field: 'origin' | 'destination', location: LocationSuggestion]
  'location-cleared': [field: 'origin' | 'destination']
}>()

const cropChoices = [
  { value: 'Tomatoes', label: 'Tomatoes' },
  { value: 'Bananas', label: 'Bananas' },
  { value: 'Mangoes', label: 'Mangoes' },
  { value: 'Leafy vegetables', label: 'Leafy vegetables' },
]
const vehicleChoices = [
  { value: 'Pickup', label: 'Pickup' },
  { value: 'Small truck', label: 'Small truck' },
  { value: 'Medium truck', label: 'Medium truck' },
]

function selectLocation(field: 'origin' | 'destination', location: LocationSuggestion) {
  emit('location-selected', field, location)
}

function clearLocation(field: 'origin' | 'destination') {
  emit('location-cleared', field)
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
      <form class="delivery-form" novalidate @submit.prevent="emit('find-routes')">
        <div class="field-grid">
          <div class="field-group">
            <Label for="crop">Crop</Label>
            <div class="select-control-wrap">
              <select id="crop" v-model="trip.crop" class="field-control" :aria-invalid="Boolean(errors.crop)" aria-describedby="crop-help crop-error">
                <option v-for="crop in cropChoices" :key="crop.value" :value="crop.value">{{ crop.label }}</option>
              </select>
              <ChevronDown class="select-chevron" :size="17" aria-hidden="true" />
            </div>
            <p id="crop-help" class="field-hint">The route advice considers this crop’s transport needs.</p>
            <p v-if="errors.crop" id="crop-error" class="field-error" role="alert">{{ errors.crop }}</p>
          </div>

          <div class="field-group">
            <Label for="quantity">Load amount</Label>
            <div class="unit-input">
              <Input id="quantity" v-model.number="trip.quantity" type="number" inputmode="numeric" min="1" step="1" required :invalid="Boolean(errors.quantity)" aria-describedby="quantity-error" />
              <span class="unit-suffix">kg</span>
            </div>
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
              :local-suggestions="demoOrigins"
              placeholder="Enter farm or pickup point"
              :invalid="Boolean(errors.origin)"
              described-by="origin-error"
              @select="selectLocation('origin', $event)"
              @clear-selection="clearLocation('origin')"
            />
            <p v-if="errors.origin" id="origin-error" class="field-error" role="alert">{{ errors.origin }}</p>
          </div>

          <div class="field-group field-span-full">
            <Label for="destination">Market or delivery point</Label>
            <LocationSearch
              id="destination"
              v-model="trip.destination"
              :local-suggestions="demoDestinations"
              icon="search"
              placeholder="Enter market or delivery point"
              :invalid="Boolean(errors.destination)"
              described-by="destination-error"
              @select="selectLocation('destination', $event)"
              @clear-selection="clearLocation('destination')"
            />
            <p v-if="errors.destination" id="destination-error" class="field-error" role="alert">{{ errors.destination }}</p>
          </div>
        </div>

        <Button type="submit" size="lg" class="w-full" :disabled="loading">
          <span v-if="loading" class="loading-dot" aria-hidden="true"></span>
          {{ loading ? 'Finding routes…' : 'Find routes' }}
        </Button>
      </form>
    </CardContent>
  </Card>
</template>
