import React from 'react'
import { btnStyle, inputStyle, sectionStyle } from './styles'

interface SessionControlsProps {
  token: string
  horseId: number
  sessionId: number | undefined
  demoBusy: boolean
  baselineRecomputeBusy: boolean
  onHorseIdChange: (id: number) => void
  onStart: () => void
  onIngestFake: () => void
  onCompute: () => void
  onStop: () => void
  onRunDemo: () => void
  onRecomputeBaseline: () => void
}

export function SessionControls({
  token,
  horseId,
  sessionId,
  demoBusy,
  baselineRecomputeBusy,
  onHorseIdChange,
  onStart,
  onIngestFake,
  onCompute,
  onStop,
  onRunDemo,
  onRecomputeBaseline,
}: SessionControlsProps) {
  return (
    <div style={sectionStyle}>
      <h3 style={{ marginTop: 0 }}>Session Controls</h3>
      <label>Horse ID</label>
      <input
        style={{ ...inputStyle, width: 80 }}
        type="number"
        value={horseId}
        onChange={(e) => onHorseIdChange(parseInt(e.target.value))}
      />

      <div style={{ marginTop: 10, display: 'flex', flexWrap: 'wrap', gap: 8 }}>
        <button style={btnStyle} onClick={onStart} disabled={!token}>
          Start Session
        </button>
        <button style={btnStyle} onClick={onIngestFake} disabled={!sessionId}>
          Ingest Fake Data
        </button>
        <button style={btnStyle} onClick={onCompute} disabled={!sessionId}>
          Compute
        </button>
        <button style={btnStyle} onClick={onStop} disabled={!sessionId}>
          Stop Session
        </button>
        <button style={btnStyle} onClick={onRunDemo} disabled={!token || demoBusy}>
          {demoBusy ? 'Running Demo…' : 'Run Demo (Start→Ingest→Compute)'}
        </button>
      </div>

      <div style={{ marginTop: 10, display: 'flex', flexWrap: 'wrap', gap: 8 }}>
        <button style={btnStyle} onClick={onRecomputeBaseline} disabled={!token || baselineRecomputeBusy}>
          {baselineRecomputeBusy ? 'Recomputing…' : `Recompute Baseline (Horse #${horseId})`}
        </button>
      </div>

      {sessionId && (
        <p style={{ color: '#555', marginBottom: 0 }}>
          Active session: <strong>#{sessionId}</strong>
        </p>
      )}
    </div>
  )
}
