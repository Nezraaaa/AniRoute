<script setup lang="ts">
import { computed } from 'vue'
import { cva } from 'class-variance-authority'
import { cn } from '@/lib/utils'

const props = withDefaults(defineProps<{
  variant?: 'default' | 'secondary' | 'outline' | 'warning' | 'danger'
  class?: string
}>(), { variant: 'default' })

const badgeStyles = cva('inline-flex min-h-7 items-center rounded-full px-2.5 py-1 text-xs font-semibold leading-none', {
  variants: {
    variant: {
      default: 'bg-emerald-100 text-emerald-950',
      secondary: 'bg-stone-100 text-stone-800',
      outline: 'border border-stone-300 bg-white text-stone-700',
      warning: 'bg-amber-100 text-amber-950',
      danger: 'bg-red-100 text-red-900',
    },
  },
  defaultVariants: { variant: 'default' },
})
const classes = computed(() => cn(badgeStyles({ variant: props.variant }), props.class))
</script>

<template>
  <span data-slot="badge" :class="classes"><slot /></span>
</template>
