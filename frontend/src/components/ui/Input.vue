<script setup lang="ts">
import { useAttrs } from 'vue'
defineOptions({ inheritAttrs: false })
const props = withDefaults(defineProps<{
  modelValue?: string | number
  type?: string
  invalid?: boolean
  class?: string
}>(), { modelValue: '', type: 'text', invalid: false })
const emit = defineEmits<{ 'update:modelValue': [value: string] }>()
const attrs = useAttrs()
</script>

<template>
  <input
    v-bind="attrs"
    :type="type"
    :value="modelValue"
    :aria-invalid="invalid ? 'true' : undefined"
    :class="['field-control', props.class]"
    @input="emit('update:modelValue', ($event.target as HTMLInputElement).value)"
  />
</template>
