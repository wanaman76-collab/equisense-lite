/**
 * useLiveFeed — React hook for subscribing to the backend live-feed WebSocket.
 *
 * Features:
 * - Maintains a bounded rolling buffer of the most recent samples.
 * - Reports connection state: connecting | live | stalled | disconnected.
 * - Reconnects with exponential backoff on transient failures.
 * - Detects stall (no samples for STALL_MS ms) and updates state accordingly.
 * - Exposes health indicators: estimated latency, effective sample rate.
 * - Supports pause/resume visualization without disconnecting the transport.
 * - Reports reconnect countdown while backing off.
 * - Hard-cleans up socket and timers on session switch (sessionId change).
 */

import { useCallback, useEffect, useRef, useState } from 'react'

import type { LiveConnectionState, LiveMessage, LiveSample } from '../types/api'

const WS_BASE: string =
  (import.meta.env.VITE_API_URL as string | undefined)?.replace(/^http/, 'ws') ??
  'ws://localhost:8000'

/** Maximum samples to keep in the rolling buffer. */
const MAX_BUFFER = 1500 // ~30 s at 50 Hz

/** After this many ms without a sample, transition to 'stalled'. */
const STALL_MS = 3000

/** Initial reconnect delay in ms (doubles each attempt, capped at MAX_BACKOFF_MS). */
const INIT_BACKOFF_MS = 1000
const MAX_BACKOFF_MS = 16000

/** Rolling window (ms) for sample-rate and latency health computation. */
const RATE_WINDOW_MS = 5000

/** Health-indicator tick interval (ms). */
const HEALTH_TICK_MS = 1000

/** A (wallClockMs, sampleCount) tuple used for rate tracking. */
type BatchRecord = [number, number]

export interface UseLiveFeedOptions {
  sessionId: number | undefined
  token: string
  /** Set to false to disconnect / pause. Defaults to true. */
  enabled?: boolean
}

export interface UseLiveFeedResult {
  samples: LiveSample[]
  connectionState: LiveConnectionState
  /** Clear the rolling buffer without disconnecting. */
  clearBuffer: () => void
  /** Pause / resume visualization. Transport stays connected while paused. */
  paused: boolean
  setPaused: (p: boolean) => void
  /**
   * Estimated end-to-end latency: `Date.now() − latest sample ts_ms` (ms).
   * `null` when no samples have arrived yet.
   */
  latencyMs: number | null
  /**
   * Effective sample rate over the last 5 s (samples / s).
   * `null` when insufficient data.
   */
  sampleRateHz: number | null
  /**
   * Milliseconds until the next reconnect attempt.
   * `null` when not in a backoff wait.
   */
  reconnectIn: number | null
}

export function useLiveFeed({
  sessionId,
  token,
  enabled = true,
}: UseLiveFeedOptions): UseLiveFeedResult {
  const [samples, setSamples] = useState<LiveSample[]>([])
  const [connectionState, setConnectionState] = useState<LiveConnectionState>('disconnected')
  const [paused, setPaused] = useState(false)
  const [latencyMs, setLatencyMs] = useState<number | null>(null)
  const [sampleRateHz, setSampleRateHz] = useState<number | null>(null)
  const [reconnectIn, setReconnectIn] = useState<number | null>(null)

  // Stable refs so callbacks inside the effect always see current state.
  const setSamplesRef = useRef(setSamples)
  setSamplesRef.current = setSamples

  const setStateRef = useRef(setConnectionState)
  setStateRef.current = setConnectionState

  // pausedRef lets the ws.onmessage closure read the latest paused value
  // without being listed as an effect dependency (which would recreate the socket).
  const pausedRef = useRef(paused)
  pausedRef.current = paused

  const clearBuffer = useCallback(() => setSamples([]), [])

  useEffect(() => {
    if (!enabled || !sessionId || !token) {
      setConnectionState('disconnected')
      setLatencyMs(null)
      setSampleRateHz(null)
      setReconnectIn(null)
      return
    }

    let alive = true
    let ws: WebSocket | null = null
    let staleTimer: ReturnType<typeof setTimeout> | null = null
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null
    let backoff = INIT_BACKOFF_MS

    // Health-indicator tracking refs (local to this effect instance).
    let lastSampleTs: number | null = null        // ts_ms of the most-recent sample
    let batchHistory: BatchRecord[] = []          // [(wallClockMs, sampleCount)]
    let reconnectDeadline: number | null = null   // wall-clock when next reconnect fires

    function armStale() {
      if (staleTimer !== null) clearTimeout(staleTimer)
      staleTimer = setTimeout(() => {
        if (alive) setStateRef.current('stalled')
      }, STALL_MS)
    }

    // Tick: update latency, sample-rate, and reconnect-countdown once per second.
    const healthTick = setInterval(() => {
      if (!alive) return
      const now = Date.now()

      // Latency
      setLatencyMs(lastSampleTs !== null ? Math.max(0, now - lastSampleTs) : null)

      // Sample rate — prune old entries first, then compute
      const cutoff = now - RATE_WINDOW_MS
      batchHistory = batchHistory.filter(([t]) => t > cutoff)
      if (batchHistory.length >= 2) {
        const totalSamples = batchHistory.reduce((s, [, c]) => s + c, 0)
        const first = batchHistory[0][0]
        const last = batchHistory[batchHistory.length - 1][0]
        const spanS = (last - first) / 1000
        setSampleRateHz(spanS > 0 ? Math.round(totalSamples / spanS) : null)
      } else {
        setSampleRateHz(null)
      }

      // Reconnect countdown
      if (reconnectDeadline !== null) {
        const remaining = reconnectDeadline - now
        setReconnectIn(remaining > 0 ? remaining : null)
      } else {
        setReconnectIn(null)
      }
    }, HEALTH_TICK_MS)

    function connect() {
      if (!alive) return
      setStateRef.current('connecting')
      reconnectDeadline = null
      setReconnectIn(null)

      const url = `${WS_BASE}/sessions/${sessionId}/live?token=${encodeURIComponent(token)}`
      ws = new WebSocket(url)

      ws.onopen = () => {
        if (!alive) return
        backoff = INIT_BACKOFF_MS
        armStale()
      }

      ws.onmessage = (event: MessageEvent) => {
        if (!alive) return
        try {
          const msg: LiveMessage = JSON.parse(event.data as string)
          if (msg.type === 'samples') {
            setStateRef.current('live')
            armStale()

            const now = Date.now()
            if (msg.readings.length > 0) {
              // Track most-recent sample timestamp for latency computation.
              lastSampleTs = msg.readings[msg.readings.length - 1].ts_ms
              // Record batch for rate computation.
              batchHistory.push([now, msg.readings.length])
            }

            if (!pausedRef.current) {
              setSamplesRef.current((prev) => {
                const next = [...prev, ...msg.readings]
                return next.length > MAX_BUFFER ? next.slice(next.length - MAX_BUFFER) : next
              })
            }
          } else if (msg.type === 'connected') {
            armStale()
          }
          // 'ping' from server: browser WebSocket keeps connection alive automatically
        } catch {
          // Ignore non-JSON frames (e.g. plain-text 'pong')
        }
      }

      ws.onerror = () => {
        // onclose fires after onerror; reconnect logic lives there
      }

      ws.onclose = () => {
        if (!alive) return
        ws = null
        if (staleTimer !== null) { clearTimeout(staleTimer); staleTimer = null }
        setStateRef.current('disconnected')
        setLatencyMs(null)
        setSampleRateHz(null)
        lastSampleTs = null
        batchHistory = []

        // Set reconnect deadline for countdown display.
        reconnectDeadline = Date.now() + backoff

        reconnectTimer = setTimeout(() => {
          reconnectDeadline = null
          backoff = Math.min(backoff * 2, MAX_BACKOFF_MS)
          connect()
        }, backoff)
      }
    }

    connect()

    return () => {
      alive = false
      clearInterval(healthTick)
      if (staleTimer !== null) clearTimeout(staleTimer)
      if (reconnectTimer !== null) clearTimeout(reconnectTimer)
      if (ws !== null) {
        ws.onclose = null // prevent reconnect on intentional teardown
        ws.close()
      }
    }
  }, [sessionId, token, enabled])

  return {
    samples,
    connectionState,
    clearBuffer,
    paused,
    setPaused,
    latencyMs,
    sampleRateHz,
    reconnectIn,
  }
}

