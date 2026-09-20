<script setup lang="ts">
defineProps<{ variant?: 'default' | 'warning' | 'danger' }>()
</script>

<template>
  <div
    data-slot="alert"
    role="status"
    :class="[
      'flex gap-3 rounded-xl border p-4 text-sm leading-relaxed',
      variant === 'warning' ? 'border-amber-300 bg-amber-50 text-amber-950' : '',
      variant === 'danger' ? 'border-red-300 bg-red-50 text-red-950' : '',
      !variant || variant === 'default' ? 'border-emerald-200 bg-emerald-50 text-emerald-950' : '',
    ]"
  >
    <slot />
  </div>
</template>
