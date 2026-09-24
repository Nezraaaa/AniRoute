<script setup lang="ts">
import aniRouteLogo from '@/assets/aniroute-logo.png'
</script>

<template>
  <div class="app-frame">
    <header class="app-topbar">
      <div class="brand-lockup" aria-label="AniRoute farm delivery planner">
        <img class="brand-logo" :src="aniRouteLogo" alt="AniRoute farm delivery planner" />
      </div>
    </header>
    <main class="app-main">
      <RouterView />
    </main>
    <footer class="app-footer">
      <span>AniRoute crop-aware transport optimizer</span>
    </footer>
  </div>
</template>
