import React from 'react'
import type { AnomalyOut, FeatureWindowOut } from '../types/api'
import { sectionStyle, tableStyle, tdStyle, thStyle } from './styles'

interface SessionDetailProps {
  sessionId: number
  features: FeatureWindowOut[]
  anomalies: AnomalyOut[]
}

export function SessionDetail({ sessionId, features, anomalies }: SessionDetailProps) {
  return (
    <>
      <div style={sectionStyle}>
        <h3 style={{ marginTop: 0 }}>Feature Windows — Session #{sessionId}</h3>
        {features.length === 0 ? (
          <p style={{ color: '#999' }}>No features computed yet.</p>
        ) : (
          <table style={tableStyle}>
            <thead>
              <tr>
                <th style={thStyle}>ID</th>
                <th style={thStyle}>ts_start</th>
                <th style={thStyle}>cadence</th>
                <th style={thStyle}>stride_var</th>
                <th style={thStyle}>asymmetry</th>
                <th style={thStyle}>energy</th>
              </tr>
            </thead>
            <tbody>
              {features.map((f) => (
                <tr key={f.id}>
                  <td style={tdStyle}>{f.id}</td>
                  <td style={tdStyle}>{f.ts_start}</td>
                  <td style={tdStyle}>{f.cadence_spm?.toFixed(2) ?? '—'}</td>
                  <td style={tdStyle}>{f.stride_var?.toFixed(4) ?? '—'}</td>
                  <td style={tdStyle}>{f.asymmetry_proxy?.toFixed(4) ?? '—'}</td>
                  <td style={tdStyle}>{f.energy?.toFixed(4) ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div style={sectionStyle}>
        <h3 style={{ marginTop: 0 }}>Anomalies — Session #{sessionId}</h3>
        {anomalies.length === 0 ? (
          <p style={{ color: '#999' }}>No anomalies detected.</p>
        ) : (
          <table style={tableStyle}>
            <thead>
              <tr>
                <th style={thStyle}>ID</th>
                <th style={thStyle}>Severity</th>
                <th style={thStyle}>Score</th>
                <th style={thStyle}>Method</th>
                <th style={thStyle}>Created</th>
              </tr>
            </thead>
            <tbody>
              {anomalies.map((a) => (
                <tr key={a.id}>
                  <td style={tdStyle}>{a.id}</td>
                  <td style={tdStyle}>{a.severity}</td>
                  <td style={tdStyle}>{a.score.toFixed(3)}</td>
                  <td style={tdStyle}>{a.method}</td>
                  <td style={tdStyle}>{new Date(a.created_at).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </>
  )
}
