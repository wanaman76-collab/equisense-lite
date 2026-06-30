/**
 * TrimPanel — Phase 7: video-style session trimming
 *
 * Displays numeric start/end trim controls with a visual timeline bar
 * showing the kept (middle) region and excluded (grey) zones on each side.
 * Calls PATCH /sessions/{id}/trim on apply and resets to full duration on reset.
 */

import React, { useCallback, useEffect, useRef, useState } from 'react'
import type { TrimOut } from '../types/api'
import { btnStyle, sectionStyle } from './styles'

interface TrimPanelProps {
  token: string
  sessionId: number
  /** Raw duration in ms (derived from sensor data; 0 if no data yet). */
  rawDurationMs: number
  /** Current trim start in ms (0 = full start). */
  initialTrimStart: number
  /** Current trim end in ms (null = full duration). */
  initialTrimEnd: number | null
  onTrimApplied: (result: TrimOut) => void
  onError: (msg: string) => void
}

const TRACK_HEIGHT = 28
const HANDLE_WIDTH = 12
const MIN_WINDOW_MS = 3_000

function msToDisplay(ms: number): string {
  const totalSec = Math.floor(ms / 1000)
  const min = Math.floor(totalSec / 60)
  const sec = totalSec % 60
  const rem = ms % 1000
  if (min > 0) return `${min}m ${sec}.${String(rem).padStart(3, '0')}s`
  return `${sec}.${String(rem).padStart(3, '0')}s`
}

export function TrimPanel({
  token,
  sessionId,
  rawDurationMs,
  initialTrimStart,
  initialTrimEnd,
  onTrimApplied,
  onError,
}: TrimPanelProps) {
  const effectiveDuration = rawDurationMs > 0 ? rawDurationMs : 0
  const clamp = (v: number) => Math.max(0, Math.min(v, effectiveDuration))

  const [trimStart, setTrimStart] = useState<number>(initialTrimStart)
  const [trimEnd, setTrimEnd] = useState<number>(
    initialTrimEnd !== null ? initialTrimEnd : effectiveDuration,
  )
  const [busy, setBusy] = useState(false)

  // Keep local state in sync when props change (e.g. after load / reset)
  useEffect(() => {
    setTrimStart(initialTrimStart)
    setTrimEnd(initialTrimEnd !== null ? initialTrimEnd : effectiveDuration)
  }, [initialTrimStart, initialTrimEnd, effectiveDuration])

  // ── Drag-handle logic ───────────────────────────────────────────────────
  const trackRef = useRef<HTMLDivElement>(null)
  const dragging = useRef<'start' | 'end' | null>(null)

  const msFromClientX = useCallback(
    (clientX: number): number => {
      if (!trackRef.current || effectiveDuration === 0) return 0
      const rect = trackRef.current.getBoundingClientRect()
      const ratio = (clientX - rect.left) / rect.width
      return clamp(Math.round(ratio * effectiveDuration))
    },
    [effectiveDuration],
  )

  const onMouseMove = useCallback(
    (e: MouseEvent) => {
      if (!dragging.current) return
      const ms = msFromClientX(e.clientX)
      if (dragging.current === 'start') {
        setTrimStart(Math.min(ms, trimEnd - MIN_WINDOW_MS))
      } else {
        setTrimEnd(Math.max(ms, trimStart + MIN_WINDOW_MS))
      }
    },
    [msFromClientX, trimStart, trimEnd],
  )

  const onMouseUp = useCallback(() => {
    dragging.current = null
    window.removeEventListener('mousemove', onMouseMove)
    window.removeEventListener('mouseup', onMouseUp)
  }, [onMouseMove])

  const startDrag = (handle: 'start' | 'end') => (e: React.MouseEvent) => {
    e.preventDefault()
    dragging.current = handle
    window.addEventListener('mousemove', onMouseMove)
    window.addEventListener('mouseup', onMouseUp)
  }

  // ── Apply / Reset ───────────────────────────────────────────────────────
  async function handleApply() {
    if (!token || busy) return
    setBusy(true)
    try {
      const { updateTrim } = await import('../api/client')
      const result = await updateTrim(token, sessionId, {
        trim_start_ms: trimStart,
        trim_end_ms: trimEnd,
      })
      onTrimApplied(result)
    } catch (e: unknown) {
      onError(e instanceof Error ? e.message : 'Trim failed')
    } finally {
      setBusy(false)
    }
  }

  async function handleReset() {
    if (!token || busy || effectiveDuration === 0) return
    setBusy(true)
    try {
      const { updateTrim } = await import('../api/client')
      const result = await updateTrim(token, sessionId, {
        trim_start_ms: 0,
        trim_end_ms: effectiveDuration,
      })
      setTrimStart(0)
      setTrimEnd(effectiveDuration)
      onTrimApplied(result)
    } catch (e: unknown) {
      onError(e instanceof Error ? e.message : 'Reset failed')
    } finally {
      setBusy(false)
    }
  }

  if (effectiveDuration === 0) {
    return (
      <div style={sectionStyle}>
        <h4 style={{ marginTop: 0 }}>✂️ Trim Session</h4>
        <p style={{ color: '#999', fontSize: 13 }}>No sensor data available to trim.</p>
      </div>
    )
  }

  // ── Derived track positions ─────────────────────────────────────────────
  const startPct = (trimStart / effectiveDuration) * 100
  const endPct = (trimEnd / effectiveDuration) * 100
  const trimmedMs = trimEnd - trimStart

  return (
    <div style={sectionStyle}>
      <h4 style={{ marginTop: 0 }}>✂️ Trim Session #{sessionId}</h4>

      <p style={{ fontSize: 13, color: '#555', marginTop: 0 }}>
        Drag the handles or adjust the values below to select the steady-state segment.
        Excluded regions (grey) are hidden from analytics; raw data is always preserved.
      </p>

      {/* Timeline track */}
      <div style={{ position: 'relative', marginBottom: 8, userSelect: 'none' }}>
        {/* Full track background */}
        <div
          ref={trackRef}
          style={{
            position: 'relative',
            height: TRACK_HEIGHT,
            background: '#ddd',
            borderRadius: 4,
            cursor: 'crosshair',
          }}
        >
          {/* Kept (middle) region */}
          <div
            style={{
              position: 'absolute',
              left: `${startPct}%`,
              width: `${endPct - startPct}%`,
              height: '100%',
              background: '#4caf50',
              opacity: 0.7,
              borderRadius: 2,
            }}
          />

          {/* Start handle */}
          <div
            onMouseDown={startDrag('start')}
            title="Drag to set trim start"
            style={{
              position: 'absolute',
              left: `calc(${startPct}% - ${HANDLE_WIDTH / 2}px)`,
              top: 0,
              width: HANDLE_WIDTH,
              height: TRACK_HEIGHT,
              background: '#1976d2',
              borderRadius: 3,
              cursor: 'ew-resize',
              zIndex: 2,
            }}
          />

          {/* End handle */}
          <div
            onMouseDown={startDrag('end')}
            title="Drag to set trim end"
            style={{
              position: 'absolute',
              left: `calc(${endPct}% - ${HANDLE_WIDTH / 2}px)`,
              top: 0,
              width: HANDLE_WIDTH,
              height: TRACK_HEIGHT,
              background: '#1976d2',
              borderRadius: 3,
              cursor: 'ew-resize',
              zIndex: 2,
            }}
          />
        </div>

        {/* Time labels */}
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: '#666', marginTop: 2 }}>
          <span>0</span>
          <span>{msToDisplay(effectiveDuration)}</span>
        </div>
      </div>

      {/* Numeric inputs */}
      <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', marginBottom: 8 }}>
        <label style={{ fontSize: 13 }}>
          Start (ms):&nbsp;
          <input
            type="number"
            min={0}
            max={trimEnd - MIN_WINDOW_MS}
            step={100}
            value={trimStart}
            onChange={(e) => setTrimStart(clamp(Number(e.target.value)))}
            style={{ width: 90, padding: '4px 6px', fontSize: 13, borderRadius: 4, border: '1px solid #aaa' }}
          />
          <span style={{ marginLeft: 6, color: '#555' }}>({msToDisplay(trimStart)})</span>
        </label>
        <label style={{ fontSize: 13 }}>
          End (ms):&nbsp;
          <input
            type="number"
            min={trimStart + MIN_WINDOW_MS}
            max={effectiveDuration}
            step={100}
            value={trimEnd}
            onChange={(e) => setTrimEnd(clamp(Number(e.target.value)))}
            style={{ width: 90, padding: '4px 6px', fontSize: 13, borderRadius: 4, border: '1px solid #aaa' }}
          />
          <span style={{ marginLeft: 6, color: '#555' }}>({msToDisplay(trimEnd)})</span>
        </label>
      </div>

      <div style={{ fontSize: 13, color: '#444', marginBottom: 10 }}>
        Kept window:{' '}
        <strong style={{ color: trimmedMs < MIN_WINDOW_MS ? 'red' : '#2e7d32' }}>
          {msToDisplay(trimmedMs)}
        </strong>
        {' '}of{' '}
        <strong>{msToDisplay(effectiveDuration)}</strong> raw duration
      </div>

      <button
        style={{ ...btnStyle, background: '#4caf50', color: '#fff', border: 'none' }}
        onClick={handleApply}
        disabled={busy || !token || trimmedMs < MIN_WINDOW_MS}
        title={trimmedMs < MIN_WINDOW_MS ? `Minimum window is ${MIN_WINDOW_MS} ms` : 'Apply trim and recompute metrics'}
      >
        {busy ? 'Applying…' : '✓ Apply Trim'}
      </button>
      <button
        style={{ ...btnStyle }}
        onClick={handleReset}
        disabled={busy || !token}
        title="Reset to full session duration"
      >
        {busy ? '…' : '↺ Reset Trim'}
      </button>
    </div>
  )
}
