import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import RouteOptionCard from './RouteOptionCard.vue'
import { makePresentationRoutes, presentationTrip } from '@/data/presentation'

describe('RouteOptionCard', () => {
  it('lets the user show a route and start the selected option', async () => {
    const route = makePresentationRoutes(presentationTrip)[1]!
    const wrapper = mount(RouteOptionCard, {
      props: { route, selected: false, crop: presentationTrip.crop },
    })

    await wrapper.get('.route-select-button').trigger('click')
    await wrapper.get('.route-actions button').trigger('click')

    expect(wrapper.emitted('select')).toEqual([[route.id]])
    expect(wrapper.emitted('use')).toEqual([[route.id]])
    expect(wrapper.text()).toContain('Safer route')
    expect(wrapper.text()).toContain('Temperature exposure')
    expect(wrapper.findAll('.risk-factor-high')).toHaveLength(2)
    expect(wrapper.findAll('.risk-factor-low')).toHaveLength(3)
  })
})
