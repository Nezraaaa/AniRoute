<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  labels: string[]
  matrix: number[][]
  normalize?: boolean
}>()

function pretty(label: string) {
  return label === 'background' ? 'Background' : label.replace(/_/g, ' ').replace(/^./, char => char.toUpperCase())
}

const rows = computed(() => props.matrix.map(row => {
  const total = row.reduce((sum, value) => sum + value, 0)
  return row.map(value => ({ value, share: total ? value / total : 0 }))
}))
const max = computed(() => Math.max(1, ...props.matrix.flat()))
</script>

<template>
  <div class="confusion-wrap">
    <table class="confusion-table">
      <caption>Rows are the true class, columns the predicted class. Background = missed object (last column) or false alarm (last row).</caption>
      <thead>
        <tr>
          <th scope="col"><span class="sr-only">True class</span></th>
          <th v-for="label in labels" :key="label" scope="col">{{ pretty(label) }}</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="(row, i) in rows" :key="labels[i]">
          <th scope="row">{{ pretty(labels[i]!) }}</th>
          <td
            v-for="(cell, j) in row"
            :key="j"
            :class="[i === j && i < labels.length - 1 ? 'confusion-diagonal' : '', i === labels.length - 1 && j === labels.length - 1 ? 'confusion-empty' : '']"
            :style="{ '--heat': normalize ? cell.share : cell.value / max }"
          >
            <template v-if="!(i === labels.length - 1 && j === labels.length - 1)">
              <strong>{{ cell.value }}</strong>
              <small v-if="i < labels.length - 1">{{ Math.round(cell.share * 100) }}%</small>
            </template>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
