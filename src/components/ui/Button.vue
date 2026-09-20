<script setup lang="ts">
import { computed, useAttrs } from 'vue'
import { cva } from 'class-variance-authority'
import { cn } from '@/lib/utils'

defineOptions({ inheritAttrs: false })

const props = withDefaults(defineProps<{
  variant?: 'default' | 'secondary' | 'outline' | 'ghost' | 'destructive'
  size?: 'default' | 'sm' | 'lg' | 'icon'
  type?: 'button' | 'submit' | 'reset'
  disabled?: boolean
  class?: string
}>(), {
  variant: 'default', size: 'default', type: 'button', disabled: false,
})
const attrs = useAttrs()

const buttonStyles = cva(
  'inline-flex shrink-0 items-center justify-center gap-2 rounded-xl text-sm font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-700 focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50',
  {
    variants: {
      variant: {
        default: 'bg-emerald-800 text-white hover:bg-emerald-900',
        secondary: 'bg-emerald-50 text-emerald-900 hover:bg-emerald-100',
        outline: 'border border-stone-300 bg-white text-stone-800 hover:bg-stone-50',
        ghost: 'bg-transparent text-stone-700 hover:bg-stone-100',
        destructive: 'bg-red-700 text-white hover:bg-red-800',
      },
      size: {
        default: 'min-h-11 px-4 py-2.5',
        sm: 'min-h-10 px-3.5 py-2',
        lg: 'min-h-12 px-5 py-3 text-base',
        icon: 'size-11',
      },
    },
    defaultVariants: { variant: 'default', size: 'default' },
  },
)

const classes = computed(() => cn(buttonStyles({ variant: props.variant, size: props.size }), props.class))
</script>

<template>
  <button v-bind="attrs" :type="type" :disabled="disabled" :class="classes">
    <slot />
  </button>
</template>
