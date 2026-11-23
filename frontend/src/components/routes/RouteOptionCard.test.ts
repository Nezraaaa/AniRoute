import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import RouteOptionCard from './RouteOptionCard.vue'
import type { RouteOption } from '@/types/aniRoute'

const route: RouteOption = {
  id: 'route-2',
  category: 'safer',
  geometry: { type: 'LineString', coordinates: [[120.596, 16.402], [121.165, 14.212]] },
  travelTimeMinutes: 365,
  distanceKm: 356.9,
  roadConditionSummary: 'No camera-confirmed road hazards on this route yet.',
  cropRiskScore: 38,
  cropRiskLabel: 'moderate',
  riskFactors: { travelTime: 68, distance: 62, crop: 65, road: 8 },
  cropProfileSummary: 'Live score for Tomatoes.',
  explanation: 'Longer, with no confirmed road hazards.',
  recommended: false,
  extraMinutes: 0,
  knownHazards: [],
  source: 'api',
}

describe('RouteOptionCard', () => {
  it('lets the user show a route and start the selected option', async () => {
    const wrapper = mount(RouteOptionCard, {
      props: { route, selected: false, crop: 'Tomatoes' },
    })

    await wrapper.get('.route-select-button').trigger('click')
    await wrapper.get('.route-actions button').trigger('click')

    expect(wrapper.emitted('select')).toEqual([[route.id]])
    expect(wrapper.emitted('use')).toEqual([[route.id]])
    expect(wrapper.text()).toContain('Safest route')
    expect(wrapper.text()).toContain('Crop')
    expect(wrapper.findAll('.risk-factor-high')).toHaveLength(3)
    expect(wrapper.findAll('.risk-factor-low')).toHaveLength(1)
  })
})
