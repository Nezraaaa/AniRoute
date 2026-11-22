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
    { path: '/vision', name: 'vision', component: () => import('@/pages/VisionLabPage.vue'), meta: { pageTitle: 'Vision Lab' } },
    { path: '/evaluation', name: 'evaluation', component: () => import('@/pages/EvaluationPage.vue'), meta: { pageTitle: 'Model evaluation' } },
    { path: '/about', name: 'about', component: () => import('@/pages/AboutPage.vue'), meta: { pageTitle: 'About' } },
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
