<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import aniRouteLogo from '@/assets/aniroute-logo.png'
import Badge from '@/components/ui/Badge.vue'
import { useAniRouteStore } from '@/composables/useAniRouteStore'
import { getJson } from '@/services/api'
import { appConfig } from '@/services/config'

const store = useAniRouteStore()
const serviceStatus = ref<'checking' | 'starting' | 'ready' | 'no-detector' | 'offline'>('checking')
let healthTimer: number | undefined

async function checkHealth() {
  try {
    const health = await getJson<{ status: string; live_hazard_detection?: boolean; vision_warming_up?: boolean }>(appConfig.paths.health, 4_000)
    serviceStatus.value = health.live_hazard_detection ? 'ready' : health.vision_warming_up ? 'starting' : 'no-detector'
    // While the models load, check again soon instead of waiting for the 20 s interval.
    if (serviceStatus.value === 'starting') window.setTimeout(checkHealth, 3_000)
  } catch {
    serviceStatus.value = 'offline'
  }
}

onMounted(() => {
  void checkHealth()
  healthTimer = window.setInterval(checkHealth, 20_000)
})
onBeforeUnmount(() => window.clearInterval(healthTimer))
</script>

<template>
  <div class="app-frame">
    <header class="app-topbar">
      <RouterLink to="/" class="brand-lockup" aria-label="AniRoute home">
        <img class="brand-logo" :src="aniRouteLogo" alt="AniRoute farm delivery planner" />
      </RouterLink>
      <nav class="app-nav" aria-label="Main">
        <RouterLink :to="store.state.activeRouteId ? '/trip/active' : '/'" class="app-nav-link" :class="{ 'app-nav-link-active': $route.name === 'plan' || $route.name === 'active-trip' }">
          {{ store.state.activeRouteId ? 'Trip' : 'Plan' }}
        </RouterLink>
        <RouterLink to="/vision" class="app-nav-link" active-class="app-nav-link-active">Vision Lab</RouterLink>
        <RouterLink to="/evaluation" class="app-nav-link" active-class="app-nav-link-active">Evaluation</RouterLink>
        <RouterLink to="/about" class="app-nav-link" active-class="app-nav-link-active">About</RouterLink>
      </nav>
      <div class="topbar-actions" aria-live="polite">
        <Badge
          :variant="serviceStatus === 'ready' ? 'default' : serviceStatus === 'checking' || serviceStatus === 'starting' ? 'secondary' : 'warning'"
          class="topbar-badge"
        >
          {{ serviceStatus === 'ready' ? 'Detector online' : serviceStatus === 'no-detector' ? 'No detection model loaded' : serviceStatus === 'offline' ? 'Backend offline' : serviceStatus === 'starting' ? 'Detector starting…' : 'Connecting…' }}
        </Badge>
      </div>
    </header>
    <main class="app-main">
      <RouterView />
    </main>
    <footer class="app-footer">
      <span>AniRoute crop-aware transport optimizer · road-hazard detection with YOLO</span>
    </footer>
  </div>
</template>
