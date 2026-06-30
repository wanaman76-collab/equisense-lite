/**
 * LiveFeedPanel — real-time sensor chart for an active session.
 *
 * Renders a rolling SVG line chart for accel magnitude and gyro magnitude
 * over a bounded window (~30 s at 50 Hz).  Shows clear state labels:
 * connecting, live, stalled, disconnected.
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

const STATE_LABEL: Record<LiveConnectionState, string> = {
  connecting: '⏳ Connecting…',
  live: '🟢 Live',
  stalled: '🟡 Stalled – no data',
  disconnected: '🔴 Disconnected – retrying…',
}

// ── Main component ────────────────────────────────────────────────────────────

export function LiveFeedPanel({ sessionId, token }: Props) {
  const { samples, connectionState, clearBuffer } = useLiveFeed({ sessionId, token })

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
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 8 }}>
        <strong>📡 Live Feed — Session #{sessionId}</strong>
        <span
          style={{
            fontSize: 12,
            color: STATE_COLOR[connectionState],
            fontWeight: 600,
          }}
        >
          {STATE_LABEL[connectionState]}
        </span>
        <button
          onClick={clearBuffer}
          style={{ marginLeft: 'auto', fontSize: 11, padding: '2px 8px', cursor: 'pointer' }}
        >
          Clear
        </button>
      </div>

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
