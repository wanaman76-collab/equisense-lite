import React from 'react'
import type { SessionOut } from '../types/api'
import { btnStyle, inputStyle, sectionStyle } from './styles'

interface SessionControlsProps {
  token: string
  horseId: number
  sessionId: number | undefined
  watchedSessionId: number | undefined
  watchSessionInput: string
  sessions: SessionOut[]
  demoBusy: boolean
  baselineRecomputeBusy: boolean
  onHorseIdChange: (id: number) => void
  onWatchSessionInputChange: (value: string) => void
  onWatchSessionSelect: (id: number | undefined) => void
  onWatchSession: () => void
  onRefreshSessions: () => void
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
  watchedSessionId,
  watchSessionInput,
  sessions,
  demoBusy,
  baselineRecomputeBusy,
  onHorseIdChange,
  onWatchSessionInputChange,
  onWatchSessionSelect,
  onWatchSession,
  onRefreshSessions,
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

      <div style={{ marginTop: 10, display: 'flex', flexWrap: 'wrap', gap: 8, alignItems: 'center' }}>
        <button style={btnStyle} onClick={onRefreshSessions} disabled={!token}>
          Refresh Sessions
        </button>
        <select
          style={{ ...inputStyle, width: 180 }}
          value={watchedSessionId?.toString() ?? ''}
          onChange={(e) => {
            if (!e.target.value) {
              onWatchSessionSelect(undefined)
              return
            }
            const parsed = parseInt(e.target.value, 10)
            onWatchSessionSelect(Number.isNaN(parsed) ? undefined : parsed)
          }}
        >
          <option value="">Select session to watch</option>
          {sessions.map((s) => (
            <option key={s.id} value={s.id}>
              #{s.id} ({s.status})
            </option>
          ))}
        </select>
        <input
          style={{ ...inputStyle, width: 140 }}
          type="number"
          min={1}
          placeholder="Session ID"
          value={watchSessionInput}
          onChange={(e) => onWatchSessionInputChange(e.target.value)}
        />
        <button style={btnStyle} onClick={onWatchSession} disabled={!token}>
          Watch Session ID
        </button>
      </div>

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
          Active recording session: <strong>#{sessionId}</strong>
        </p>
      )}

      {watchedSessionId && (
        <p style={{ color: '#555', marginBottom: 0 }}>
          Watching live session: <strong>#{watchedSessionId}</strong>
        </p>
      )}
    </div>
  )
}
