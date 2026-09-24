import { describe, expect, it } from 'vitest'
import { parseVoiceCommand } from './useVoiceRecognition'

describe('parseVoiceCommand', () => {
  it('recognizes confirmation phrases', () => {
    expect(parseVoiceCommand('confirm and upload')).toBe('confirm')
    expect(parseVoiceCommand('yes, save it')).toBe('confirm')
  })

  it('recognizes dismissal phrases', () => {
    expect(parseVoiceCommand('not now')).toBe('dismiss')
    expect(parseVoiceCommand('cancel this finding')).toBe('dismiss')
  })

  it('ignores unrelated speech', () => {
    expect(parseVoiceCommand('what is the weather')).toBeNull()
  })
})
