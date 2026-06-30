/**
 * LiveFeedPanel — real-time sensor chart for an active session.
 *
 * Renders a rolling SVG line chart for accel magnitude and gyro magnitude
 * over a bounded window (~30 s at 50 Hz).  Shows clear state labels:
 * connecting, live, stalled, disconnected.
 *
 * Phase 6.1 additions:
 * - Live health bar: connection state, effective sample rate, estimated latency.
 * - Pause / resume visualization without disconnecting the transport.
 * - Reconnect countdown during exponential-backoff waits.
 */

import React, { useMemo } from 'react'

import { useLiveFeed } from '../hooks/useLiveFeed'
import type { LiveConnectionState, LiveSample } from '../types/api'
import { sectionStyle } from './styles'

interface Props {
  sessionId: number
  token: string
}

// ── Tiny inline SVG line chart ────────────────────────────────────────────────

interface ChartProps {
  values: number[]
  color: string
  maxY: number
  height?: number
}

function MiniChart({ values, color, maxY, height = 60 }: ChartProps) {
  const width = 500
  const pts = useMemo(() => {
    if (values.length < 2) return ''
    const step = width / (values.length - 1)
    return values
      .map((v, i) => {
        const x = i * step
        const y = height - Math.min(Math.max(v, 0), maxY) * (height / maxY)
        return `${x.toFixed(1)},${y.toFixed(1)}`
      })
      .join(' ')
  }, [values, height, maxY])

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      style={{ width: '100%', height: height, display: 'block', background: '#111' }}
      preserveAspectRatio="none"
    >
      {pts && <polyline points={pts} fill="none" stroke={color} strokeWidth="1.5" />}
    </svg>
  )
}

// ── Status badge ──────────────────────────────────────────────────────────────

const STATE_COLOR: Record<LiveConnectionState, string> = {
  connecting: '#aaa',
  live: '#4caf50',
  stalled: '#ff9800',
  disconnected: '#f44336',
}

function statusLabel(
  state: LiveConnectionState,
  reconnectIn: number | null,
): string {
  if (state === 'disconnected') {
    if (reconnectIn !== null && reconnectIn > 0) {
      return `🔴 Disconnected – retry in ${Math.ceil(reconnectIn / 1000)}s`
    }
    return '🔴 Disconnected – retrying…'
  }
  const labels: Record<LiveConnectionState, string> = {
    connecting: '⏳ Connecting…',
    live: '🟢 Live',
    stalled: '🟡 Stalled – no data',
    disconnected: '🔴 Disconnected',
  }
  return labels[state]
}

// ── Main component ────────────────────────────────────────────────────────────

export function LiveFeedPanel({ sessionId, token }: Props) {
  const {
    samples,
    connectionState,
    clearBuffer,
    paused,
    setPaused,
    latencyMs,
    sampleRateHz,
    reconnectIn,
  } = useLiveFeed({ sessionId, token })

  const accelMag = useMemo(
    () =>
      samples.map((s: LiveSample) =>
        Math.sqrt(s.ax * s.ax + s.ay * s.ay + s.az * s.az),
      ),
    [samples],
  )

  const gyroMag = useMemo(
    () =>
      samples.map((s: LiveSample) =>
        Math.sqrt(s.gx * s.gx + s.gy * s.gy + s.gz * s.gz),
      ),
    [samples],
  )

  return (
    <div style={sectionStyle}>
      {/* ── Header row ── */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 6 }}>
        <strong>📡 Live Feed — Session #{sessionId}</strong>
        <span
          style={{
            fontSize: 12,
            color: STATE_COLOR[connectionState],
            fontWeight: 600,
          }}
        >
          {statusLabel(connectionState, reconnectIn)}
        </span>
        <button
          onClick={() => setPaused(!paused)}
          title={paused ? 'Resume visualization' : 'Pause visualization (transport stays connected)'}
          style={{ marginLeft: 'auto', fontSize: 11, padding: '2px 8px', cursor: 'pointer' }}
        >
          {paused ? '▶ Resume' : '⏸ Pause'}
        </button>
        <button
          onClick={clearBuffer}
          style={{ fontSize: 11, padding: '2px 8px', cursor: 'pointer' }}
        >
          Clear
        </button>
      </div>

      {/* ── Health bar ── */}
      <div
        style={{
          display: 'flex',
          gap: 16,
          fontSize: 11,
          color: '#888',
          marginBottom: 8,
          flexWrap: 'wrap',
        }}
      >
        <span>
          Rate:{' '}
          <span style={{ color: '#ccc' }}>
            {sampleRateHz !== null ? `${sampleRateHz} Hz` : '—'}
          </span>
        </span>
        <span>
          Latency:{' '}
          <span
            style={{
              color:
                latencyMs === null
                  ? '#ccc'
                  : latencyMs < 500
                  ? '#4caf50'
                  : latencyMs < 2000
                  ? '#ff9800'
                  : '#f44336',
            }}
          >
            {latencyMs !== null ? `${latencyMs} ms` : '—'}
          </span>
        </span>
        <span>
          Buffer:{' '}
          <span style={{ color: '#ccc' }}>{samples.length} samples</span>
        </span>
        {paused && (
          <span style={{ color: '#ff9800', fontWeight: 600 }}>⏸ Paused</span>
        )}
      </div>

      {/* ── Charts ── */}
      {samples.length === 0 && connectionState !== 'disconnected' ? (
        <p style={{ color: '#888', fontSize: 13, margin: 0 }}>
          Waiting for live samples from the recording device…
        </p>
      ) : (
        <>
          <div style={{ marginBottom: 6 }}>
            <div style={{ fontSize: 11, color: '#aaa', marginBottom: 2 }}>
              Accel magnitude (g) — last {samples.length} samples
            </div>
            <MiniChart values={accelMag} color="#4caf50" maxY={2} />
          </div>
          <div>
            <div style={{ fontSize: 11, color: '#aaa', marginBottom: 2 }}>
              Gyro magnitude (rad/s)
            </div>
            <MiniChart values={gyroMag} color="#2196f3" maxY={10} />
          </div>
        </>
      )}
    </div>
  )
}
