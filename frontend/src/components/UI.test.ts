import { describe, expect, it } from 'vitest'
import { labelColor } from '../components/UI'

describe('labelColor', () => {
  it('returns green for NORMAL', () => {
    expect(labelColor('NORMAL')).toBe('#d4edda')
  })

  it('returns yellow for WATCH', () => {
    expect(labelColor('WATCH')).toBe('#fff3cd')
  })

  it('returns red for IRREGULAR', () => {
    expect(labelColor('IRREGULAR')).toBe('#f8d7da')
  })

  it('returns red for unknown labels', () => {
    expect(labelColor('UNKNOWN')).toBe('#f8d7da')
  })
})
