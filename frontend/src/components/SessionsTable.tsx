import React from 'react'
import type { SessionOut } from '../types/api'
import { btnStyle, sectionStyle, tableStyle, tdStyle, thStyle } from './styles'

interface SessionsTableProps {
  token: string
  sessions: SessionOut[]
  selectedSessionId: number | undefined
  baselineBusySessionId: number | null
  onRefresh: () => void
  onViewSession: (id: number) => void
  onMarkBaseline: (id: number) => void
}

export function SessionsTable({
  token,
  sessions,
  selectedSessionId,
  baselineBusySessionId,
  onRefresh,
  onViewSession,
  onMarkBaseline,
}: SessionsTableProps) {
  return (
    <div style={sectionStyle}>
      <h3 style={{ marginTop: 0 }}>Sessions</h3>
      <button style={btnStyle} onClick={onRefresh} disabled={!token}>
        Refresh
      </button>

      {sessions.length > 0 && (
        <table style={tableStyle}>
          <thead>
            <tr>
              <th style={thStyle}>#</th>
              <th style={thStyle}>Status</th>
              <th style={thStyle}>Started</th>
              <th style={thStyle}>Baseline</th>
              <th style={thStyle}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {sessions.map((s) => (
              <tr key={s.id} style={{ background: selectedSessionId === s.id ? '#fffde7' : undefined }}>
                <td style={tdStyle}>{s.id}</td>
                <td style={tdStyle}>{s.status}</td>
                <td style={tdStyle}>{new Date(s.started_at).toLocaleString()}</td>
                <td style={tdStyle}>{s.is_baseline ? '✓' : '—'}</td>
                <td style={tdStyle}>
                  <button
                    style={{ ...btnStyle, padding: '4px 10px', fontSize: 13, marginTop: 0 }}
                    onClick={() => onViewSession(s.id)}
                  >
                    View
                  </button>
                  <button
                    style={{ ...btnStyle, padding: '4px 10px', fontSize: 13, marginTop: 0 }}
                    onClick={() => onMarkBaseline(s.id)}
                    disabled={!token || baselineBusySessionId === s.id}
                    title="Mark this session as a baseline session for its horse."
                  >
                    {baselineBusySessionId === s.id ? 'Marking…' : 'Mark Baseline'}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <p style={{ marginTop: 10, color: '#666', fontSize: 12 }}>
        Tip: Mark 3–5 good trot sessions as baseline, then recompute baseline for the horse.
      </p>
    </div>
  )
}
