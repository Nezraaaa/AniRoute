import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import DeliveryForm from './DeliveryForm.vue'
import { demoTrip } from '@/data/demo'

describe('DeliveryForm', () => {
  it('shows place suggestions and submits the trip details', async () => {
    const wrapper = mount(DeliveryForm, {
      props: { trip: { ...demoTrip }, errors: {} },
    })

    expect(wrapper.get('#origin').attributes('list')).toBe('origin-suggestions')
    expect(wrapper.get('#destination').attributes('list')).toBe('destination-suggestions')
    expect(wrapper.findAll('#origin-suggestions option')).toHaveLength(3)

    await wrapper.get('form').trigger('submit')
    expect(wrapper.emitted('find-routes')).toHaveLength(1)
  })
})
