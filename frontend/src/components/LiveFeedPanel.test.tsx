/**
 * Tests for useLiveFeed hook and LiveFeedPanel component.
 *
 * Covers:
 * - Initial disconnected state
 * - Connection state transitions (connecting → live → stalled)
 * - Bounded rolling buffer (MAX_BUFFER respected)
 * - clearBuffer clears samples
 * - LiveFeedPanel renders status labels
 * - Phase 6.1: pause/resume visualization
 * - Phase 6.1: latency and sample-rate indicators
 * - Phase 6.1: reconnect countdown
 * - Phase 6.1: session-switch hard cleanup (no stale sockets)
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

function makeSample(ts_ms = 1000) {
  return { ts_ms, ax: 0.1, ay: 0.0, az: 0.0, gx: 0.0, gy: 0.0, gz: 0.0 }
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
        readings: [makeSample()],
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
        readings: [makeSample()],
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
    const readings = Array.from({ length: 1600 }, (_, i) => makeSample(i))
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
        readings: [makeSample()],
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

  // ── Phase 6.1: pause/resume ───────────────────────────────────────────────

  it('does not add samples to buffer while paused', () => {
    const { result } = renderHook(() =>
      useLiveFeed({ sessionId: 1, token: 'dev-token' }),
    )
    const ws = latestWs()

    act(() => ws.simulateOpen())

    // Pause before any samples arrive
    act(() => result.current.setPaused(true))
    expect(result.current.paused).toBe(true)

    act(() =>
      ws.simulateMessage({
        type: 'samples',
        session_id: 1,
        readings: [makeSample()],
      }),
    )

    // Buffer should remain empty while paused
    expect(result.current.samples).toHaveLength(0)
    // Connection state should still be 'live'
    expect(result.current.connectionState).toBe<LiveConnectionState>('live')
  })

  it('resumes adding samples after unpause', () => {
    const { result } = renderHook(() =>
      useLiveFeed({ sessionId: 1, token: 'dev-token' }),
    )
    const ws = latestWs()

    act(() => ws.simulateOpen())
    act(() => result.current.setPaused(true))

    // Sample arrives while paused → discarded
    act(() =>
      ws.simulateMessage({ type: 'samples', session_id: 1, readings: [makeSample(100)] }),
    )
    expect(result.current.samples).toHaveLength(0)

    // Resume
    act(() => result.current.setPaused(false))

    // Sample arrives after resume → buffered
    act(() =>
      ws.simulateMessage({ type: 'samples', session_id: 1, readings: [makeSample(200)] }),
    )
    expect(result.current.samples).toHaveLength(1)
  })

  it('starts with paused=false', () => {
    const { result } = renderHook(() =>
      useLiveFeed({ sessionId: 1, token: 'dev-token' }),
    )
    expect(result.current.paused).toBe(false)
  })

  // ── Phase 6.1: health indicators ─────────────────────────────────────────

  it('returns null latencyMs and sampleRateHz initially', () => {
    const { result } = renderHook(() =>
      useLiveFeed({ sessionId: 1, token: 'dev-token' }),
    )
    expect(result.current.latencyMs).toBeNull()
    expect(result.current.sampleRateHz).toBeNull()
  })

  it('updates latencyMs after the health tick fires', () => {
    // Use a real epoch-ms timestamp so latency = Date.now() - ts_ms > 0
    const nowMs = Date.now()
    const { result } = renderHook(() =>
      useLiveFeed({ sessionId: 1, token: 'dev-token' }),
    )
    const ws = latestWs()

    act(() => {
      ws.simulateOpen()
      // Simulate a sample with a ts_ms slightly in the past
      ws.simulateMessage({
        type: 'samples',
        session_id: 1,
        readings: [makeSample(nowMs - 200)],
      })
    })

    // Advance 1 s to trigger the health tick
    act(() => {
      vi.advanceTimersByTime(1000)
    })

    expect(result.current.latencyMs).not.toBeNull()
    expect(result.current.latencyMs).toBeGreaterThanOrEqual(0)
  })

  it('clears latencyMs and sampleRateHz when socket closes', () => {
    const nowMs = Date.now()
    const { result } = renderHook(() =>
      useLiveFeed({ sessionId: 1, token: 'dev-token' }),
    )
    const ws = latestWs()

    act(() => {
      ws.simulateOpen()
      ws.simulateMessage({
        type: 'samples',
        session_id: 1,
        readings: [makeSample(nowMs - 200)],
      })
    })

    act(() => { vi.advanceTimersByTime(1000) })

    act(() => ws.simulateClose())

    expect(result.current.latencyMs).toBeNull()
    expect(result.current.sampleRateHz).toBeNull()
  })

  // ── Phase 6.1: reconnect countdown ───────────────────────────────────────

  it('exposes non-null reconnectIn while waiting to reconnect', () => {
    const { result } = renderHook(() =>
      useLiveFeed({ sessionId: 1, token: 'dev-token' }),
    )
    const ws = latestWs()

    // Advance 1 ms first so the close timestamp is offset from the health-tick
    // boundary.  If close happened at t=0 and backoff=1000ms, both the health
    // tick and the reconnect timer would fire simultaneously at t=1000ms giving
    // remaining=0 → null.  With close at t=1ms the reconnect fires at t=1001ms,
    // while the health tick fires at t=1000ms with remaining=1ms > 0.
    act(() => { vi.advanceTimersByTime(1) })
    act(() => ws.simulateClose())

    // Health tick fires at t=1000ms; reconnectDeadline=1001ms, remaining=1ms > 0.
    act(() => { vi.advanceTimersByTime(999) })

    expect(result.current.reconnectIn).not.toBeNull()
  })

  // ── Phase 6.1: session-switch cleanup ────────────────────────────────────

  it('closes old socket and opens new one on sessionId change', () => {
    const { rerender } = renderHook(
      ({ sessionId }: { sessionId: number }) =>
        useLiveFeed({ sessionId, token: 'dev-token' }),
      { initialProps: { sessionId: 1 } },
    )

    expect(wsInstances).toHaveLength(1)
    const firstWs = wsInstances[0]

    // Switch session — should close old socket and open a new one
    act(() => rerender({ sessionId: 2 }))

    // Old socket must be closed (readyState CLOSED)
    expect(firstWs.readyState).toBe(MockWebSocket.CLOSED)
    // A new socket should have been created
    expect(wsInstances).toHaveLength(2)
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

  it('renders pause button', () => {
    const { container } = render(<LiveFeedPanel sessionId={42} token="dev-token" />)
    expect(container.textContent).toContain('Pause')
  })

  it('shows health bar fields', () => {
    const { container } = render(<LiveFeedPanel sessionId={42} token="dev-token" />)
    expect(container.textContent).toContain('Rate:')
    expect(container.textContent).toContain('Latency:')
    expect(container.textContent).toContain('Buffer:')
  })
})

