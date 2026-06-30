/**
 * TypeScript types matching the EquiSense Lite backend API schemas.
 * Keep in sync with backend/app/schemas.py
 */

export type SessionStatus = 'DRAFT' | 'COMPLETED'
export type TrotConfidence = 'LOW' | 'MEDIUM' | 'HIGH'
export type OverallLabel = 'NORMAL' | 'WATCH' | 'IRREGULAR'
export type AnomalyMethod = 'STATS' | 'FUSION'
export type Severity = 'LOW' | 'MEDIUM' | 'HIGH'

export interface HorseOut {
  id: number
  name: string
  notes: string | null
}

export interface SessionOut {
  id: number
  horse_id: number
  surface: string | null
  notes: string | null
  started_at: string
  stopped_at: string | null
  status: SessionStatus
  is_baseline: boolean | null
}

export interface IngestItem {
  ts_ms: number
  ax: number
  ay: number
  az: number
  gx: number
  gy: number
  gz: number
}

export interface IngestBatch {
  session_id: number
  readings: IngestItem[]
}

export interface IngestResponse {
  stored: number
}

export interface FeatureWindowOut {
  id: number
  ts_start: number
  ts_end: number
  cadence_spm: number | null
  stride_var: number | null
  asymmetry_proxy: number | null
  energy: number | null
  quality_flags: string | null
}

export interface AnomalyOutEmbed {
  score: number
  severity: Severity
  method: AnomalyMethod
}

export interface FeatureWindowExport extends FeatureWindowOut {
  anomaly: AnomalyOutEmbed | null
}

export interface AnomalyOut {
  id: number
  window_id: number
  method: AnomalyMethod
  score: number
  severity: Severity
  details_json: Record<string, unknown> | null
  created_at: string
}

export interface ComputeReportMetrics {
  cadence_spm_mean: number | null
  cadence_spm_std: number | null
  stride_var_median: number | null
  stride_var_iqr: number | null
  asymmetry_proxy_median: number | null
  asymmetry_proxy_iqr: number | null
  energy_mean: number | null
  windows_with_gaps: number
}

export interface ComputeReportBaseline {
  cadence_spm_median: number | null
  cadence_spm_mad: number | null
  stride_var_median: number | null
  stride_var_mad: number | null
  asymmetry_proxy_median: number | null
  asymmetry_proxy_mad: number | null
}

export interface ComputeReport {
  overall_label: OverallLabel
  trot_confidence: TrotConfidence
  explanations: string[]
  metrics: ComputeReportMetrics
  baseline: ComputeReportBaseline
}

export interface ComputeResponse {
  windows: number
  anomalies_total: number
  anomalies_medium_high: number
  report: ComputeReport
}
