import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import DeliveryForm from './DeliveryForm.vue'
import { demoTrip } from '@/data/demo'

describe('DeliveryForm', () => {
  it('shows place suggestions and submits the trip details', async () => {
    const wrapper = mount(DeliveryForm, {
      props: { trip: { ...demoTrip }, errors: {} },
    })

    expect(wrapper.get('#crop-count').attributes('type')).toBe('number')
    expect(wrapper.get('#destination-count').attributes('type')).toBe('number')
    expect(wrapper.get('#vehicle').text()).toContain('Motorcycle / Habal-habal')
    expect(wrapper.findAll('#crop-0')).toHaveLength(0)
    expect(wrapper.findAll('#destination-0')).toHaveLength(0)

    await wrapper.get('#crop-count').setValue('2')
    expect(wrapper.get('#crop-0').attributes('placeholder')).toBe('Enter crop name')
    expect(wrapper.findAll('#crop-1')).toHaveLength(1)

    await wrapper.get('#destination-count').setValue('2')
    expect(wrapper.get('#destination-0').attributes('list')).toBe('destination-0-suggestions')
    expect(wrapper.findAll('#destination-1')).toHaveLength(1)
    expect(wrapper.get('#origin').attributes('list')).toBe('origin-suggestions')
    expect(wrapper.findAll('#origin-suggestions option')).toHaveLength(3)

    await wrapper.get('form').trigger('submit')
    expect(wrapper.emitted('find-routes')).toHaveLength(1)
  })
})
