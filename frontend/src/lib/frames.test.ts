import { describe, expect, it } from 'vitest'
import { projectBox } from './frames'

describe('projectBox', () => {
  it('maps a normalised box into a letterboxed (contain) container', () => {
    // 1280x720 video shown in a 640x640 box → 640x360 picture with 140 px bars top and bottom.
    const rect = projectBox([0.5, 0.5, 0.75, 1], { width: 640, height: 640 }, { width: 1280, height: 720 }, 'contain')
    expect(rect).toEqual({ left: 320, top: 140 + 180, width: 160, height: 180 })
  })

  it('maps a box into a cropped (cover) portrait preview', () => {
    // 1280x720 video filling a 360x640 portrait box: scale 640/720, cropped left and right.
    const rect = projectBox([0.5, 0, 0.5, 1], { width: 360, height: 640 }, { width: 1280, height: 720 }, 'cover')
    const shownWidth = 1280 * (640 / 720)
    expect(rect.left).toBeCloseTo((360 - shownWidth) / 2 + shownWidth / 2)
    expect(rect.top).toBeCloseTo(0)
    expect(rect.height).toBeCloseTo(640)
  })

  it('returns an empty rect before the media size is known', () => {
    expect(projectBox([0, 0, 1, 1], { width: 100, height: 100 }, { width: 0, height: 0 }, 'contain'))
      .toEqual({ left: 0, top: 0, width: 0, height: 0 })
  })
})
