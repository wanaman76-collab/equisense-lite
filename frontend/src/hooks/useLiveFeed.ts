/**
 * useLiveFeed — React hook for subscribing to the backend live-feed WebSocket.
 *
 * Features:
 * - Maintains a bounded rolling buffer of the most recent samples.
 * - Reports connection state: connecting | live | stalled | disconnected.
 * - Reconnects with exponential backoff on transient failures.
 * - Detects stall (no samples for STALL_MS ms) and updates state accordingly.
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
}

export function useLiveFeed({
  sessionId,
  token,
  enabled = true,
}: UseLiveFeedOptions): UseLiveFeedResult {
  const [samples, setSamples] = useState<LiveSample[]>([])
  const [connectionState, setConnectionState] = useState<LiveConnectionState>('disconnected')

  // Stable ref so the setSamples callback inside the effect always writes to
  // the current state without needing to be listed as a dependency.
  const setSamplesRef = useRef(setSamples)
  setSamplesRef.current = setSamples

  const setStateRef = useRef(setConnectionState)
  setStateRef.current = setConnectionState

  const clearBuffer = useCallback(() => setSamples([]), [])

  useEffect(() => {
    if (!enabled || !sessionId || !token) {
      setConnectionState('disconnected')
      return
    }

    let alive = true
    let ws: WebSocket | null = null
    let staleTimer: ReturnType<typeof setTimeout> | null = null
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null
    let backoff = INIT_BACKOFF_MS

    function armStale() {
      if (staleTimer !== null) clearTimeout(staleTimer)
      staleTimer = setTimeout(() => {
        if (alive) setStateRef.current('stalled')
      }, STALL_MS)
    }

    function connect() {
      if (!alive) return
      setStateRef.current('connecting')

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
            setSamplesRef.current((prev) => {
              const next = [...prev, ...msg.readings]
              return next.length > MAX_BUFFER ? next.slice(next.length - MAX_BUFFER) : next
            })
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

        // Exponential backoff reconnect
        reconnectTimer = setTimeout(() => {
          backoff = Math.min(backoff * 2, MAX_BACKOFF_MS)
          connect()
        }, backoff)
      }
    }

    connect()

    return () => {
      alive = false
      if (staleTimer !== null) clearTimeout(staleTimer)
      if (reconnectTimer !== null) clearTimeout(reconnectTimer)
      if (ws !== null) {
        ws.onclose = null // prevent reconnect on intentional teardown
        ws.close()
      }
    }
  }, [sessionId, token, enabled])

  return { samples, connectionState, clearBuffer }
}

