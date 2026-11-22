import { afterEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, h } from 'vue'
import { mount } from '@vue/test-utils'
import { useFrameScanner } from './useFrameScanner'

vi.mock('@/lib/frames', () => ({ captureVideoFrame: () => 'data:image/jpeg;base64,/9j/AA==' }))

function fakeVideo(paused = false) {
  return { paused, ended: false } as unknown as HTMLVideoElement
}

function mountScanner(send: (frame: string) => Promise<string>, video: HTMLVideoElement | null) {
  let api!: ReturnType<typeof useFrameScanner<string>>
  const results: string[] = []
  mount(defineComponent({
    setup() {
      api = useFrameScanner<string>({ getVideo: () => video, send, onResult: value => results.push(value), intervalMs: 60_000 })
      return () => h('div')
    },
  }))
  return { api, results }
}

afterEach(() => vi.useRealTimers())

describe('useFrameScanner', () => {
  it('sends a captured frame and reports the result', async () => {
    const send = vi.fn().mockResolvedValue('ok')
    const { api, results } = mountScanner(send, fakeVideo())
    api.start()
    await api.tickNow()
    expect(send).toHaveBeenCalledWith('data:image/jpeg;base64,/9j/AA==')
    expect(results).toEqual(['ok'])
    expect(api.framesSent.value).toBe(1)
    api.stop()
  })

  it('skips ticks while a request is still in flight instead of queueing frames', async () => {
    let release!: (value: string) => void
    const send = vi.fn().mockImplementation(() => new Promise<string>(resolve => { release = resolve }))
    const { api } = mountScanner(send, fakeVideo())
    api.start()
    const first = api.tickNow()
    await Promise.resolve()
    expect(api.inFlight.value).toBe(true)
    await api.tickNow()
    expect(send).toHaveBeenCalledTimes(1)
    expect(api.framesSkipped.value).toBe(1)
    release('done')
    await first
    expect(api.inFlight.value).toBe(false)
    api.stop()
  })

  it('does not send frames from a paused video', async () => {
    const send = vi.fn().mockResolvedValue('ok')
    const { api } = mountScanner(send, fakeVideo(true))
    api.start()
    await api.tickNow()
    expect(send).not.toHaveBeenCalled()
    api.stop()
  })

  it('records errors without stopping the loop', async () => {
    const send = vi.fn().mockRejectedValue(new Error('Server busy'))
    const { api } = mountScanner(send, fakeVideo())
    api.start()
    await api.tickNow()
    expect(api.lastError.value).toBe('Server busy')
    expect(api.running.value).toBe(true)
    api.stop()
  })
})
