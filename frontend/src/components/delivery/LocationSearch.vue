<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { LoaderCircle, MapPin, Search } from '@lucide/vue'
import Input from '@/components/ui/Input.vue'
import { searchLocations } from '@/services/geocoding'
import type { LocationSuggestion } from '@/types/aniRoute'

const props = withDefaults(defineProps<{
  id: string
  modelValue: string
  placeholder: string
  icon?: 'pin' | 'search'
  invalid?: boolean
  describedBy?: string
}>(), {
  icon: 'pin',
  invalid: false,
  describedBy: undefined,
})

const emit = defineEmits<{
  'update:modelValue': [value: string]
  select: [location: LocationSuggestion]
  'clear-selection': []
}>()

const query = ref(props.modelValue)
const suggestions = ref<LocationSuggestion[]>([])
const searching = ref(false)
const open = ref(false)
const focused = ref(false)
const activeIndex = ref(-1)
const searchErrorMessage = ref('')
let searchTimer: number | undefined
let requestController: AbortController | undefined

const listId = computed(() => `${props.id}-location-list`)
const datalistId = computed(() => `${props.id}-suggestions`)
const hasNoMatches = computed(() => open.value && !searching.value && !searchErrorMessage.value && query.value.trim().length >= 2 && suggestions.value.length === 0)

watch(() => props.modelValue, value => {
  if (value !== query.value) query.value = value
})

function scheduleSearch(value: string) {
  if (searchTimer) window.clearTimeout(searchTimer)
  requestController?.abort()
  searching.value = false
  activeIndex.value = -1
  searchErrorMessage.value = ''
  suggestions.value = []
  open.value = value.trim().length >= 2
  if (value.trim().length < 2) return

  searchTimer = window.setTimeout(() => { void runSearch(value) }, 300)
}

async function runSearch(value: string) {
  const controller = new AbortController()
  requestController = controller
  searching.value = true
  open.value = focused.value
  try {
    const remoteSuggestions = await searchLocations(value, controller.signal)
    if (controller.signal.aborted) return
    suggestions.value = remoteSuggestions
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') return
    suggestions.value = []
    searchErrorMessage.value = error instanceof Error
      ? error.message
      : 'Location search is unavailable. Check the internet connection and try again.'
  } finally {
    if (!controller.signal.aborted) searching.value = false
  }
}

function handleInput(value: string) {
  query.value = value
  emit('update:modelValue', value)
  emit('clear-selection')
  scheduleSearch(value)
}

function handleFocus() {
  focused.value = true
  if (query.value.trim().length >= 2) {
    open.value = true
    scheduleSearch(query.value)
  }
}

function handleBlur() {
  focused.value = false
  window.setTimeout(() => {
    if (!focused.value) open.value = false
  }, 120)
}

function handleKeydown(event: KeyboardEvent) {
  if (!open.value || !suggestions.value.length) {
    if (event.key === 'Escape') open.value = false
    return
  }
  if (event.key === 'ArrowDown') {
    event.preventDefault()
    activeIndex.value = (activeIndex.value + 1) % suggestions.value.length
  } else if (event.key === 'ArrowUp') {
    event.preventDefault()
    activeIndex.value = activeIndex.value <= 0 ? suggestions.value.length - 1 : activeIndex.value - 1
  } else if (event.key === 'Enter' && activeIndex.value >= 0) {
    event.preventDefault()
    choose(suggestions.value[activeIndex.value])
  } else if (event.key === 'Escape') {
    event.preventDefault()
    open.value = false
  }
}

function choose(location: LocationSuggestion) {
  query.value = location.displayName
  emit('update:modelValue', location.displayName)
  emit('select', location)
  open.value = false
  activeIndex.value = -1
}

function primaryLabel(displayName: string) {
  return displayName.split(',')[0]?.trim() || displayName
}

function secondaryLabel(location: LocationSuggestion) {
  return location.type || location.category || 'OpenStreetMap place result'
}

onBeforeUnmount(() => {
  if (searchTimer) window.clearTimeout(searchTimer)
  requestController?.abort()
})
</script>

<template>
  <div class="location-search">
    <div class="select-with-icon location-search-control">
      <MapPin v-if="icon === 'pin'" :size="17" aria-hidden="true" />
      <Search v-else :size="17" aria-hidden="true" />
      <Input
        :id="id"
        :model-value="query"
        :list="datalistId"
        :class="searching ? 'field-control-icon location-search-input-searching' : 'field-control-icon'"
        autocomplete="off"
        :placeholder="placeholder"
        required
        :invalid="invalid"
        :aria-describedby="describedBy"
        aria-autocomplete="list"
        :aria-controls="listId"
        :aria-expanded="open ? 'true' : 'false'"
        :aria-activedescendant="activeIndex >= 0 ? `${listId}-${activeIndex}` : undefined"
        @update:model-value="handleInput"
        @focus="handleFocus"
        @blur="handleBlur"
        @keydown="handleKeydown"
      />
      <LoaderCircle v-if="searching" class="location-search-spinner" :size="17" aria-label="Searching locations" />
    </div>

    <div v-if="open && (suggestions.length || searching || hasNoMatches || searchErrorMessage)" :id="listId" class="location-suggestions" role="listbox" :aria-label="`${id} location suggestions`">
      <div v-if="searching" class="location-suggestion-status" role="status">
        <LoaderCircle :size="15" aria-hidden="true" /> Searching locations…
      </div>
      <div v-else-if="searchErrorMessage" class="location-suggestion-status location-suggestion-error" role="alert">
        {{ searchErrorMessage }}
      </div>
      <template v-else>
        <button
          v-for="(location, index) in suggestions"
          :id="`${listId}-${index}`"
          :key="location.id"
          type="button"
          class="location-suggestion"
          :class="{ 'location-suggestion-active': index === activeIndex }"
          role="option"
          :aria-selected="index === activeIndex ? 'true' : 'false'"
          @mousedown.prevent
          @click="choose(location)"
        >
          <MapPin :size="16" aria-hidden="true" />
          <span class="location-suggestion-copy">
            <strong>{{ primaryLabel(location.displayName) }}</strong>
            <small>{{ location.displayName }} · {{ secondaryLabel(location) }}</small>
          </span>
        </button>
        <div v-if="!suggestions.length" class="location-suggestion-status">No matching locations found. Try a nearby town, farm, or market.</div>
      </template>
    </div>

    <datalist :id="datalistId">
      <option v-for="location in suggestions" :key="`remote-${location.id}`" :value="location.displayName" />
    </datalist>
  </div>
</template>
