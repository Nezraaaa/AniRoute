import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import HazardConfirmation from './HazardConfirmation.vue'
import type { DetectedHazard } from '@/types/aniRoute'

const hazard: DetectedHazard = {
  id: 'sample-pothole', type: 'pothole', detectedAt: '2026-09-20T12:30:00.000Z',
  coordinates: { latitude: 6.42, longitude: 124.89 }, routeId: 'optimal',
  roadSegmentId: 'optimal-segment-2', distanceAheadKm: 0.4, simulated: true,
}

function makeDialog() {
  return mount(HazardConfirmation, {
    props: {
      open: true, hazard, detectedFrame: 'data:image/png;base64,ZGVtby1mcmFtZQ==', uploadStatus: 'idle', uploadMessage: '',
      nearbyName: 'Koronadal trading post',
    },
    global: {
      stubs: {
        Dialog: { template: '<div><slot /></div>' },
        DialogTitle: { template: '<h2><slot /></h2>' },
        DialogDescription: { template: '<p><slot /></p>' },
      },
    },
  })
}

describe('HazardConfirmation', () => {
  it('dismisses without confirming or uploading the finding', async () => {
    const wrapper = makeDialog()

    await wrapper.get('[data-testid="hazard-dismiss-button"]').trigger('click')

    expect(wrapper.emitted('dismiss')).toHaveLength(1)
    expect(wrapper.emitted('confirm')).toBeUndefined()
  })

  it('confirms and requests immediate upload in one action', async () => {
    const wrapper = makeDialog()

    await wrapper.get('[data-testid="hazard-confirm-button"]').trigger('click')

    expect(wrapper.emitted('confirm')).toEqual([['data:image/png;base64,ZGVtby1mcmFtZQ==']])
    expect(wrapper.text()).toContain('Confirm & upload')
    expect(wrapper.get('img').attributes('src')).toContain('data:image/png')
  })
})
