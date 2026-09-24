import { createRouter, createWebHistory } from 'vue-router'
import PlanPage from '@/pages/PlanPage.vue'
import ActiveTripPage from '@/pages/ActiveTripPage.vue'
import { useAniRouteStore } from '@/composables/useAniRouteStore'

declare module 'vue-router' {
  interface RouteMeta {
    pageTitle: string
  }
}

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'plan', component: PlanPage, meta: { pageTitle: 'Plan a delivery' } },
    { path: '/trip/active', name: 'active-trip', component: ActiveTripPage, meta: { pageTitle: 'Active trip' } },
  ],
  scrollBehavior() {
    return { top: 0 }
  },
})

router.beforeEach(to => {
  if (to.name === 'active-trip' && !useAniRouteStore().state.activeRouteId) return { name: 'plan' }
})

router.afterEach(to => {
  document.title = `AniRoute | ${to.meta.pageTitle}`
})
