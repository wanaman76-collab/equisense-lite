import React from 'react'
import type { AnomalyOut, ComputeResponse } from '../types/api'
import { Badge, labelColor } from './UI'
import { btnStyle, tableStyle, tdStyle, thStyle } from './styles'

interface SeverityCounts {
  LOW: number
  MEDIUM: number
  HIGH: number
}

function severityCounts(anoms: AnomalyOut[]): SeverityCounts {
  const counts: SeverityCounts = { LOW: 0, MEDIUM: 0, HIGH: 0 }
  for (const a of anoms) {
    if (a.severity === 'LOW') counts.LOW++
    else if (a.severity === 'MEDIUM') counts.MEDIUM++
    else if (a.severity === 'HIGH') counts.HIGH++
  }
  return counts
}

interface ComputeReportSectionProps {
  computeResult: ComputeResponse
  anomalies: AnomalyOut[]
  demoLastSessionId: number | null
  onExportCsv: (id: number) => void
}

export function ComputeReportSection({
  computeResult,
  anomalies,
  demoLastSessionId,
  onExportCsv,
}: ComputeReportSectionProps) {
  const report = computeResult.report
  const counts = severityCounts(anomalies)
  const totalSeverity = counts.LOW + counts.MEDIUM + counts.HIGH

  return (
    <div
      style={{
        marginBottom: 24,
        padding: '16px',
        border: '1px solid #ddd',
        borderRadius: 8,
      }}
    >
      <h3 style={{ marginTop: 0 }}>
        Session Report
        {report.overall_label && <Badge text={report.overall_label} color={labelColor(report.overall_label)} />}
        {report.trot_confidence && <Badge text={`Trot: ${report.trot_confidence}`} color="#e2e3ff" />}

        {demoLastSessionId && (
          <button
            style={{ ...btnStyle, padding: '6px 10px', fontSize: 13, marginTop: 0 }}
            onClick={() => onExportCsv(demoLastSessionId)}
            title="Download computed windows + anomaly fields as CSV."
          >
            Export CSV
          </button>
        )}
      </h3>

      <p style={{ marginTop: 8, color: '#444' }}>
        Windows: <strong>{computeResult.windows}</strong> · Anomalies:{' '}
        <strong>{computeResult.anomalies_total}</strong> · Med/High:{' '}
        <strong>{computeResult.anomalies_medium_high}</strong>
      </p>

      {totalSeverity > 0 && (
        <div style={{ marginTop: 10 }}>
          <h4 style={{ marginBottom: 6 }}>Severity summary</h4>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <Badge text={`LOW: ${counts.LOW}`} color="#d4edda" />
            <Badge text={`MEDIUM: ${counts.MEDIUM}`} color="#fff3cd" />
            <Badge text={`HIGH: ${counts.HIGH}`} color="#f8d7da" />
          </div>
        </div>
      )}

      {report.explanations.length > 0 && (
        <>
          <h4 style={{ marginBottom: 6 }}>Notes</h4>
          <ul style={{ marginTop: 0 }}>
            {report.explanations.map((x, i) => (
              <li key={i}>{x}</li>
            ))}
          </ul>
        </>
      )}

      <h4 style={{ marginBottom: 6 }}>Metrics</h4>
      <table style={{ ...tableStyle, fontSize: 13 }}>
        <thead>
          <tr>
            <th style={thStyle}>Metric</th>
            <th style={thStyle}>Value</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td style={tdStyle}>Cadence mean</td>
            <td style={tdStyle}>{report.metrics.cadence_spm_mean?.toFixed(1) ?? '—'}</td>
          </tr>
          <tr>
            <td style={tdStyle}>Cadence std</td>
            <td style={tdStyle}>{report.metrics.cadence_spm_std?.toFixed(1) ?? '—'}</td>
          </tr>
          <tr>
            <td style={tdStyle}>Stride var median</td>
            <td style={tdStyle}>{report.metrics.stride_var_median?.toFixed(4) ?? '—'}</td>
          </tr>
          <tr>
            <td style={tdStyle}>Asymmetry median</td>
            <td style={tdStyle}>{report.metrics.asymmetry_proxy_median?.toFixed(4) ?? '—'}</td>
          </tr>
          <tr>
            <td style={tdStyle}>Energy mean</td>
            <td style={tdStyle}>{report.metrics.energy_mean?.toFixed(4) ?? '—'}</td>
          </tr>
          <tr>
            <td style={tdStyle}>Windows with gaps</td>
            <td style={tdStyle}>{report.metrics.windows_with_gaps}</td>
          </tr>
        </tbody>
      </table>

      <h4 style={{ marginBottom: 6, marginTop: 14 }}>Baseline used</h4>
      <table style={{ ...tableStyle, fontSize: 13 }}>
        <thead>
          <tr>
            <th style={thStyle}>Feature</th>
            <th style={thStyle}>Median</th>
            <th style={thStyle}>MAD</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td style={tdStyle}>cadence_spm</td>
            <td style={tdStyle}>{report.baseline.cadence_spm_median?.toFixed(1) ?? '—'}</td>
            <td style={tdStyle}>{report.baseline.cadence_spm_mad?.toFixed(3) ?? '—'}</td>
          </tr>
          <tr>
            <td style={tdStyle}>stride_var</td>
            <td style={tdStyle}>{report.baseline.stride_var_median?.toFixed(4) ?? '—'}</td>
            <td style={tdStyle}>{report.baseline.stride_var_mad?.toFixed(4) ?? '—'}</td>
          </tr>
          <tr>
            <td style={tdStyle}>asymmetry_proxy</td>
            <td style={tdStyle}>{report.baseline.asymmetry_proxy_median?.toFixed(4) ?? '—'}</td>
            <td style={tdStyle}>{report.baseline.asymmetry_proxy_mad?.toFixed(4) ?? '—'}</td>
          </tr>
        </tbody>
      </table>
    </div>
  )
}
