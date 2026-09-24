import { defineComponent } from 'vue'
import { mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useVoiceRecognition } from './useVoiceRecognition'

class FakeSpeechRecognition {
  static instances: FakeSpeechRecognition[] = []
  lang = ''
  continuous = false
  interimResults = false
  maxAlternatives = 0
  startCalls = 0
  stopCalls = 0
  abortCalls = 0
  onstart: (() => void) | null = null
  onend: (() => void) | null = null
  onresult: ((event: { results: { length: number; 0: { 0: { transcript: string } } } }) => void) | null = null
  onerror: ((event: { error: string }) => void) | null = null

  constructor() {
    FakeSpeechRecognition.instances.push(this)
  }

  start() {
    this.startCalls += 1
    this.onstart?.()
  }

  stop() {
    this.stopCalls += 1
    this.onend?.()
  }

  abort() {
    this.abortCalls += 1
  }

  emitEnd() {
    this.onend?.()
  }

  emitResult(transcript: string) {
    this.onresult?.({ results: { length: 1, 0: { 0: { transcript } } } })
  }
}

function mountVoiceHarness(onCommand = vi.fn()) {
  let voice: ReturnType<typeof useVoiceRecognition> | undefined
  const wrapper = mount(defineComponent({
    setup() {
      voice = useVoiceRecognition(onCommand)
      return {}
    },
    template: '<div />',
  }))
  return { wrapper, voice: voice!, onCommand }
}

describe('useVoiceRecognition lifecycle', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    FakeSpeechRecognition.instances = []
    Object.defineProperty(window, 'SpeechRecognition', {
      configurable: true,
      writable: true,
      value: FakeSpeechRecognition,
    })
  })

  afterEach(() => {
    vi.useRealTimers()
    Object.defineProperty(window, 'SpeechRecognition', {
      configurable: true,
      writable: true,
      value: undefined,
    })
  })

  it('restarts listening after the browser ends a recognition session', () => {
    const { wrapper, voice } = mountVoiceHarness()

    expect(voice.start()).toBe(true)
    const recognition = FakeSpeechRecognition.instances[0]!
    recognition.emitEnd()
    vi.advanceTimersByTime(250)

    expect(recognition.startCalls).toBe(2)
    expect(voice.isListening.value).toBe(true)
    wrapper.unmount()
  })

  it('stops restarting after a voice command is received', () => {
    const { wrapper, voice, onCommand } = mountVoiceHarness()

    voice.start()
    const recognition = FakeSpeechRecognition.instances[0]!
    recognition.emitResult('confirm')
    vi.advanceTimersByTime(1_000)

    expect(onCommand).toHaveBeenCalledWith('confirm')
    expect(recognition.startCalls).toBe(1)
    wrapper.unmount()
  })
})
