/**
 * Tests for useLiveFeed hook and LiveFeedPanel component.
 *
 * Covers:
 * - Initial disconnected state
 * - Connection state transitions (connecting → live → stalled)
 * - Bounded rolling buffer (MAX_BUFFER respected)
 * - clearBuffer clears samples
 * - LiveFeedPanel renders status labels
 */

import { act, cleanup, render, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import React from 'react'

import { useLiveFeed } from '../hooks/useLiveFeed'
import { LiveFeedPanel } from './LiveFeedPanel'
import type { LiveConnectionState } from '../types/api'

// ── WebSocket mock ─────────────────────────────────────────────────────────────

class MockWebSocket {
  static CONNECTING = 0
  static OPEN = 1
  static CLOSING = 2
  static CLOSED = 3

  readyState = MockWebSocket.CONNECTING
  url: string
  onopen: (() => void) | null = null
  onmessage: ((e: { data: string }) => void) | null = null
  onerror: (() => void) | null = null
  onclose: (() => void) | null = null

  constructor(url: string) {
    this.url = url
  }

  send(_data: string) {}
  close() {
    this.readyState = MockWebSocket.CLOSED
    this.onclose?.()
  }

  // Test helpers
  simulateOpen() {
    this.readyState = MockWebSocket.OPEN
    this.onopen?.()
  }

  simulateMessage(data: unknown) {
    this.onmessage?.({ data: JSON.stringify(data) })
  }

  simulateClose() {
    this.readyState = MockWebSocket.CLOSED
    this.onclose?.()
  }
}

let wsInstances: MockWebSocket[] = []

beforeEach(() => {
  wsInstances = []
  vi.stubGlobal(
    'WebSocket',
    class extends MockWebSocket {
      constructor(url: string) {
        super(url)
        wsInstances.push(this as unknown as MockWebSocket)
      }
    },
  )
  vi.useFakeTimers()
})

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
  vi.useRealTimers()
})

function latestWs(): MockWebSocket {
  return wsInstances[wsInstances.length - 1]
}

// ── useLiveFeed tests ──────────────────────────────────────────────────────────

describe('useLiveFeed', () => {
  it('starts disconnected when no sessionId', () => {
    const { result } = renderHook(() =>
      useLiveFeed({ sessionId: undefined, token: 'dev-token' }),
    )
    expect(result.current.connectionState).toBe<LiveConnectionState>('disconnected')
    expect(result.current.samples).toHaveLength(0)
  })

  it('transitions to connecting when sessionId provided', () => {
    const { result } = renderHook(() =>
      useLiveFeed({ sessionId: 1, token: 'dev-token' }),
    )
    expect(result.current.connectionState).toBe<LiveConnectionState>('connecting')
  })

  it('transitions to live on receiving samples', () => {
    const { result } = renderHook(() =>
      useLiveFeed({ sessionId: 1, token: 'dev-token' }),
    )
    const ws = latestWs()

    act(() => {
      ws.simulateOpen()
      ws.simulateMessage({
        type: 'samples',
        session_id: 1,
        readings: [{ ts_ms: 1000, ax: 0.1, ay: 0.0, az: 0.0, gx: 0.0, gy: 0.0, gz: 0.0 }],
      })
    })

    expect(result.current.connectionState).toBe<LiveConnectionState>('live')
    expect(result.current.samples).toHaveLength(1)
  })

  it('transitions to stalled after no samples for STALL_MS', () => {
    const { result } = renderHook(() =>
      useLiveFeed({ sessionId: 1, token: 'dev-token' }),
    )
    const ws = latestWs()

    act(() => {
      ws.simulateOpen()
      ws.simulateMessage({
        type: 'samples',
        session_id: 1,
        readings: [{ ts_ms: 1000, ax: 0.1, ay: 0, az: 0, gx: 0, gy: 0, gz: 0 }],
      })
    })

    // Advance past the 3 s stall threshold
    act(() => {
      vi.advanceTimersByTime(4000)
    })

    expect(result.current.connectionState).toBe<LiveConnectionState>('stalled')
  })

  it('enforces MAX_BUFFER limit on samples', () => {
    const { result } = renderHook(() =>
      useLiveFeed({ sessionId: 1, token: 'dev-token' }),
    )
    const ws = latestWs()

    act(() => ws.simulateOpen())

    // Send 1600 readings (> MAX_BUFFER of 1500) in one shot
    const readings = Array.from({ length: 1600 }, (_, i) => ({
      ts_ms: i,
      ax: 0,
      ay: 0,
      az: 0,
      gx: 0,
      gy: 0,
      gz: 0,
    }))
    act(() => ws.simulateMessage({ type: 'samples', session_id: 1, readings }))

    expect(result.current.samples.length).toBeLessThanOrEqual(1500)
  })

  it('clearBuffer empties samples without disconnecting', () => {
    const { result } = renderHook(() =>
      useLiveFeed({ sessionId: 1, token: 'dev-token' }),
    )
    const ws = latestWs()

    act(() => {
      ws.simulateOpen()
      ws.simulateMessage({
        type: 'samples',
        session_id: 1,
        readings: [{ ts_ms: 1, ax: 1, ay: 0, az: 0, gx: 0, gy: 0, gz: 0 }],
      })
    })

    expect(result.current.samples).toHaveLength(1)

    act(() => result.current.clearBuffer())

    expect(result.current.samples).toHaveLength(0)
    expect(result.current.connectionState).toBe<LiveConnectionState>('live')
  })

  it('transitions to disconnected when socket closes', () => {
    const { result } = renderHook(() =>
      useLiveFeed({ sessionId: 1, token: 'dev-token' }),
    )
    const ws = latestWs()

    act(() => {
      ws.simulateClose()
      // Fake timers prevent the reconnect setTimeout from firing,
      // so state stays 'disconnected' until timers are advanced.
    })

    expect(result.current.connectionState).toBe<LiveConnectionState>('disconnected')
  })
})

// ── LiveFeedPanel render tests ─────────────────────────────────────────────────

describe('LiveFeedPanel', () => {
  it('renders session id in header', () => {
    const { container } = render(<LiveFeedPanel sessionId={42} token="dev-token" />)
    expect(container.textContent).toContain('42')
  })

  it('shows connecting status label initially', () => {
    const { container } = render(<LiveFeedPanel sessionId={42} token="dev-token" />)
    expect(container.textContent).toContain('Connecting')
  })

  it('shows waiting message when no samples yet', () => {
    const { container } = render(<LiveFeedPanel sessionId={42} token="dev-token" />)
    expect(container.textContent).toContain('Waiting for live samples')
  })
})

