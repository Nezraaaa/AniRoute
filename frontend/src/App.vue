<script setup lang="ts">
import { computed } from 'vue'
import Badge from '@/components/ui/Badge.vue'
import { useAniRouteStore } from '@/composables/useAniRouteStore'
import type { AppMode } from '@/types/aniRoute'
import aniRouteLogo from '@/assets/aniroute-logo.png'

const store = useAniRouteStore()
const mode = computed(() => store.state.mode)

function setMode(nextMode: AppMode) {
  store.state.mode = nextMode
}
</script>

<template>
  <div class="app-frame">
    <header class="app-topbar">
      <div class="brand-lockup" aria-label="AniRoute farm delivery planner">
        <img class="brand-logo" :src="aniRouteLogo" alt="AniRoute farm delivery planner" />
      </div>
      <div class="topbar-actions">
        <div class="mode-switch" role="group" aria-label="Route data mode">
          <span class="mode-switch-label">Data mode</span>
          <div class="mode-switch-control">
            <button
              type="button"
              :class="['mode-switch-option', mode === 'demo' ? 'mode-switch-option-active' : '']"
              :aria-pressed="mode === 'demo'"
              @click="setMode('demo')"
            >Demo</button>
            <button
              type="button"
              :class="['mode-switch-option', mode === 'live' ? 'mode-switch-option-active' : '']"
              :aria-pressed="mode === 'live'"
              @click="setMode('live')"
            >Live</button>
          </div>
        </div>
        <Badge variant="secondary" class="topbar-badge">{{ mode === 'demo' ? 'Demo mode' : 'Live mode' }}</Badge>
      </div>
    </header>
    <main class="app-main">
      <RouterView />
    </main>
    <footer class="app-footer">
      <span>AniRoute {{ mode === 'demo' ? 'demo experience' : 'live integration' }}</span>
      <span>{{ mode === 'demo' ? 'Demo routes and risk levels are not live road advice.' : 'Live routes, risk data and detection require the backend.' }}</span>
    </footer>
  </div>
</template>
