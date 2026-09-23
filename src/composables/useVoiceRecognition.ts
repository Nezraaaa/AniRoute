import { onBeforeUnmount, onMounted, ref } from 'vue'

export type VoiceCommand = 'confirm' | 'dismiss'

interface SpeechRecognitionAlternativeLike {
  transcript: string
}

interface SpeechRecognitionResultLike {
  0: SpeechRecognitionAlternativeLike
}

interface SpeechRecognitionResultListLike {
  length: number
  [index: number]: SpeechRecognitionResultLike | undefined
}

interface SpeechRecognitionResultEventLike {
  results: SpeechRecognitionResultListLike
}

interface SpeechRecognitionErrorEventLike {
  error: string
}

interface BrowserSpeechRecognition {
  lang: string
  continuous: boolean
  interimResults: boolean
  maxAlternatives: number
  start: () => void
  stop: () => void
  abort: () => void
  onstart: (() => void) | null
  onend: (() => void) | null
  onresult: ((event: SpeechRecognitionResultEventLike) => void) | null
  onerror: ((event: SpeechRecognitionErrorEventLike) => void) | null
}

type SpeechRecognitionConstructor = new () => BrowserSpeechRecognition
type SpeechRecognitionWindow = Window & {
  SpeechRecognition?: SpeechRecognitionConstructor
  webkitSpeechRecognition?: SpeechRecognitionConstructor
}

function getSpeechRecognitionConstructor() {
  if (typeof window === 'undefined') return undefined
  const speechWindow = window as SpeechRecognitionWindow
  return speechWindow.SpeechRecognition || speechWindow.webkitSpeechRecognition
}

export function parseVoiceCommand(transcript: string): VoiceCommand | null {
  const normalized = transcript.toLowerCase().replace(/[^\p{L}\p{N}\s]/gu, ' ').replace(/\s+/g, ' ').trim()
  if (!normalized) return null

  if (/\b(not now|cancel|dismiss|decline|reject|no)\b/.test(normalized)) return 'dismiss'
  if (/\b(confirm|confirmed|approve|approved|accept|accepted|yes|save|upload)\b/.test(normalized)) return 'confirm'
  return null
}

function messageForSpeechError(errorCode: string) {
  switch (errorCode) {
    case 'not-allowed':
    case 'service-not-allowed':
      return 'Microphone permission was blocked. Allow it, then try voice confirmation again.'
    case 'no-speech':
      return 'No voice command was heard. Say “confirm” or “not now” and try again.'
    case 'audio-capture':
      return 'No microphone was found. Use the buttons below to confirm manually.'
    case 'network':
      return 'The browser voice service is unavailable. Use the buttons below to confirm manually.'
    default:
      return 'Voice recognition stopped. Use the buttons below or try again.'
  }
}

export function useVoiceRecognition(onCommand: (command: VoiceCommand) => void) {
  const isSupported = ref(false)
  const isListening = ref(false)
  const transcript = ref('')
  const errorMessage = ref('')
  let recognition: BrowserSpeechRecognition | null = null
  let commandHandled = false
  let shouldContinue = false
  let restartTimer: number | undefined

  function clearRestartTimer() {
    if (restartTimer === undefined) return
    window.clearTimeout(restartTimer)
    restartTimer = undefined
  }

  function scheduleRestart() {
    if (!shouldContinue || commandHandled || restartTimer !== undefined || typeof window === 'undefined') return
    restartTimer = window.setTimeout(() => {
      restartTimer = undefined
      if (!shouldContinue || commandHandled || isListening.value || !recognition) return
      try {
        recognition.start()
        isListening.value = true
      } catch {
        scheduleRestart()
      }
    }, 250)
  }

  function setup() {
    const Recognition = getSpeechRecognitionConstructor()
    isSupported.value = Boolean(Recognition)
    if (!Recognition) return null
    if (recognition) return recognition

    const instance = new Recognition()
    instance.lang = 'en-US'
    instance.continuous = false
    instance.interimResults = true
    instance.maxAlternatives = 1
    instance.onstart = () => {
      isListening.value = true
      errorMessage.value = ''
    }
    instance.onresult = event => {
      let nextTranscript = ''
      for (let index = 0; index < event.results.length; index += 1) {
        const result = event.results[index]
        if (result?.[0]?.transcript) nextTranscript += `${result[0].transcript} `
      }
      transcript.value = nextTranscript.trim()
      const command = parseVoiceCommand(transcript.value)
      if (command && !commandHandled) {
        commandHandled = true
        shouldContinue = false
        clearRestartTimer()
        instance.stop()
        onCommand(command)
      }
    }
    instance.onerror = event => {
      isListening.value = false
      if (event.error === 'aborted') return
      if (event.error === 'no-speech') {
        errorMessage.value = ''
        scheduleRestart()
        return
      }
      shouldContinue = false
      clearRestartTimer()
      errorMessage.value = messageForSpeechError(event.error)
    }
    instance.onend = () => {
      isListening.value = false
      scheduleRestart()
    }
    recognition = instance
    return instance
  }

  function start() {
    if (isListening.value) return true
    const instance = setup()
    if (!instance) {
      errorMessage.value = 'Voice recognition is not supported in this browser. Use the buttons below to confirm manually.'
      return false
    }
    shouldContinue = true
    clearRestartTimer()
    commandHandled = false
    transcript.value = ''
    errorMessage.value = ''
    try {
      instance.start()
      isListening.value = true
      return true
    } catch {
      isListening.value = false
      scheduleRestart()
      return false
    }
  }

  function stop() {
    shouldContinue = false
    clearRestartTimer()
    if (recognition) {
      try {
        recognition.stop()
      } catch {
        // The browser may throw if recognition has already ended.
      }
    }
    isListening.value = false
  }

  function reset() {
    stop()
    transcript.value = ''
    errorMessage.value = ''
  }

  onMounted(() => {
    isSupported.value = Boolean(getSpeechRecognitionConstructor())
  })
  onBeforeUnmount(() => {
    shouldContinue = false
    clearRestartTimer()
    if (recognition) {
      try {
        recognition.abort()
      } catch {
        // Ignore cleanup errors from the browser speech service.
      }
    }
  })

  return { isSupported, isListening, transcript, errorMessage, start, stop, reset }
}
