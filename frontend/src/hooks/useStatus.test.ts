import { describe, expect, it } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useStatus } from '../hooks/useStatus'

describe('useStatus', () => {
  it('starts with empty message', () => {
    const { result } = renderHook(() => useStatus())
    expect(result.current.status.message).toBe('')
    expect(result.current.status.ok).toBe(true)
  })

  it('sets status message and ok=true by default', () => {
    const { result } = renderHook(() => useStatus())
    act(() => {
      result.current.setStatus('all good')
    })
    expect(result.current.status.message).toBe('all good')
    expect(result.current.status.ok).toBe(true)
  })

  it('sets status message and ok=false when specified', () => {
    const { result } = renderHook(() => useStatus())
    act(() => {
      result.current.setStatus('something failed', false)
    })
    expect(result.current.status.message).toBe('something failed')
    expect(result.current.status.ok).toBe(false)
  })
})
