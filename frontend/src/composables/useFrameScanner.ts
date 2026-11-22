import { onBeforeUnmount, ref } from 'vue'
import { captureVideoFrame } from '@/lib/frames'

export interface FrameScannerOptions<T> {
  /** Returns the element to sample; null skips the tick. */
  getVideo: () => HTMLVideoElement | null
  /** Sends one frame to the detector. */
  send: (frameDataUrl: string) => Promise<T>
  onResult: (result: T) => void
  onError?: (error: unknown) => void
  intervalMs?: number
  maxWidth?: number
  quality?: number
}

/**
 * Samples a video element on a fixed interval and sends frames to the detector.
 *
 * Only one request is in flight at a time: when the server is slower than the
 * interval, ticks are skipped instead of queueing (no backpressure pile-up).
 * Sampling pauses while the tab is hidden or the video is paused.
 */
export function useFrameScanner<T>(options: FrameScannerOptions<T>) {
  const running = ref(false)
  const inFlight = ref(false)
  const latencyMs = ref<number | null>(null)
  const fps = ref<number | null>(null)
  const framesSent = ref(0)
  const framesSkipped = ref(0)
  const lastError = ref('')
  let timer: number | undefined
  const completions: number[] = []

  function schedule() {
    if (!running.value) return
    timer = window.setTimeout(tick, options.intervalMs ?? 600)
  }

  async function tick() {
    timer = undefined
    if (!running.value) return
    const video = options.getVideo()
    const hidden = typeof document !== 'undefined' && document.visibilityState === 'hidden'
    if (inFlight.value) {
      framesSkipped.value += 1
      schedule()
      return
    }
    if (!video || hidden || video.paused || video.ended) {
      schedule()
      return
    }
    const frame = captureVideoFrame(video, options.maxWidth ?? 640, options.quality ?? 0.7)
    if (!frame) {
      schedule()
      return
    }
    inFlight.value = true
    const started = performance.now()
    try {
      const result = await options.send(frame)
      const now = performance.now()
      latencyMs.value = Math.round(now - started)
      completions.push(now)
      while (completions.length && now - completions[0]! > 5_000) completions.shift()
      fps.value = completions.length > 1 ? Number(((completions.length - 1) / ((now - completions[0]!) / 1000)).toFixed(1)) : null
      framesSent.value += 1
      lastError.value = ''
      if (running.value) options.onResult(result)
    } catch (error) {
      lastError.value = error instanceof Error ? error.message : 'Frame analysis failed.'
      options.onError?.(error)
    } finally {
      inFlight.value = false
      schedule()
    }
  }

  function start() {
    if (running.value) return
    running.value = true
    lastError.value = ''
    schedule()
  }

  function stop() {
    running.value = false
    if (timer) window.clearTimeout(timer)
    timer = undefined
    completions.length = 0
    fps.value = null
  }

  /** Test hook: run one tick immediately. */
  async function tickNow() {
    if (timer) window.clearTimeout(timer)
    await tick()
  }

  onBeforeUnmount(stop)
  return { running, inFlight, latencyMs, fps, framesSent, framesSkipped, lastError, start, stop, tickNow }
}
