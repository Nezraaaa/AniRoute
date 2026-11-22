import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import DetectionOverlay from './DetectionOverlay.vue'
import { mapDetectResult, mapModelInfo } from '@/services/vision'
import type { VisionDetection } from '@/types/aniRoute'

const detection: VisionDetection = {
  id: 'd1', hazardType: 'pothole', label: 'Pothole', sourceLabel: 'pothole', confidence: 0.87,
  box: [600, 520, 760, 600], boxNorm: [0.46875, 0.7222, 0.59375, 0.8333], model: 'A',
}

describe('DetectionOverlay', () => {
  it('renders one labelled, colour-coded box per detection', () => {
    const wrapper = mount(DetectionOverlay, { props: { detections: [detection], mediaWidth: 1280, mediaHeight: 720 } })
    const box = wrapper.get('[data-hazard="pothole"]')
    expect(box.attributes('aria-label')).toBe('Pothole, 87% confidence')
    expect(box.text()).toContain('Pothole 87%')
    expect(box.attributes('style')).toContain('border-color')
  })
})

describe('vision adapters', () => {
  it('maps snake_case detection results', () => {
    const result = mapDetectResult({
      detections: [{ id: 'x', hazard_type: 'severe_road_damage', label: 'Severe road damage', source_label: 'severe_road_damage',
        confidence: 0.5, box: [1, 2, 3, 4], box_norm: [0.1, 0.2, 0.3, 0.4], model: 'A' }],
      image: { width: 640, height: 480 },
      timings_ms: { total: 52.1 },
      models_used: ['A', 'B'],
      roi_rejected: 2,
      preprocessing: { clahe_applied: true, luminance_mean: 61.2, luminance_std: 30.4 },
    })
    expect(result.detections[0]).toMatchObject({ hazardType: 'severe_road_damage', boxNorm: [0.1, 0.2, 0.3, 0.4] })
    expect(result.preprocessing).toEqual({ claheApplied: true, luminanceMean: 61.2, luminanceStd: 30.4 })
    expect(result.roiRejected).toBe(2)
  })

  it('maps model info including the driving corridor', () => {
    const status = { name: 'A', weights: 'a.pt', loaded: false, available: false, runtime_format: null, classes: [], error: 'Weights not found' }
    const info = mapModelInfo({
      ready: true, warming_up: false, supported_hazards: ['road_obstruction'], manual_only_hazards: ['pothole', 'severe_road_damage', 'standing_water'],
      models: { A: status, B: { ...status, name: 'B', loaded: true, available: true, runtime_format: 'openvino', error: null } },
      thresholds: { model_a_confidence: 0.35, model_b_confidence: 0.45, nms_iou: 0.5 },
      imgsz: 640, device: 'cpu',
      roi: { top: 0.4, bottom_half_width: 0.25, top_half_width: 0.1, min_height: 0.12 },
      smoothing: { window: 3, min_hits: 2, cooldown_seconds: 20, dedupe_meters: 50 },
      hazard_labels: { pothole: 'Pothole', severe_road_damage: 'Severe road damage', standing_water: 'Standing water', road_obstruction: 'Road obstruction' },
      hazard_colors: { pothole: '#F59E0B', severe_road_damage: '#DC2626', standing_water: '#2563EB', road_obstruction: '#7C3AED' },
      evaluated: false,
    })
    expect(info.corridor).toEqual({ top: 0.4, bottomHalfWidth: 0.25, topHalfWidth: 0.1, minHeight: 0.12 })
    expect(info.models.B.runtimeFormat).toBe('openvino')
    expect(info.smoothing.minHits).toBe(2)
  })
})
