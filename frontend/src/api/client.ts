/**
 * Typed API client for EquiSense Lite backend.
 * All HTTP calls go through this module.
 */

import type {
  AnomalyOut,
  ComputeResponse,
  FeatureWindowExport,
  FeatureWindowOut,
  HorseOut,
  IngestBatch,
  IngestResponse,
  SessionOut,
  TrimIn,
  TrimOut,
} from '../types/api'

const API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

async function request<T>(path: string, token: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      'X-API-Token': token,
      ...(init.headers ?? {}),
    },
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }))
    throw new ApiError(res.status, (body as { detail?: string }).detail ?? res.statusText)
  }
  return res.json() as Promise<T>
}

// ── Horses ──────────────────────────────────────────────────────────────────

export function createHorse(token: string, name: string, notes?: string): Promise<HorseOut> {
  return request<HorseOut>('/horses', token, {
    method: 'POST',
    body: JSON.stringify({ name, notes }),
  })
}

// ── Sessions ─────────────────────────────────────────────────────────────────

export function startSession(token: string, horseId: number, surface?: string): Promise<SessionOut> {
  return request<SessionOut>('/sessions', token, {
    method: 'POST',
    body: JSON.stringify({ horse_id: horseId, surface }),
  })
}

export function stopSession(token: string, sessionId: number): Promise<SessionOut> {
  return request<SessionOut>(`/sessions/${sessionId}/stop`, token, { method: 'POST' })
}

export function listSessions(token: string): Promise<SessionOut[]> {
  return request<SessionOut[]>('/sessions', token)
}

export function markBaseline(token: string, sessionId: number, enabled: boolean): Promise<SessionOut> {
  return request<SessionOut>(`/sessions/${sessionId}/baseline`, token, {
    method: 'POST',
    body: JSON.stringify({ enabled }),
  })
}

export function computeSession(token: string, sessionId: number): Promise<ComputeResponse> {
  return request<ComputeResponse>(`/sessions/${sessionId}/compute`, token, { method: 'POST' })
}

export function getFeatures(token: string, sessionId: number): Promise<FeatureWindowOut[]> {
  return request<FeatureWindowOut[]>(`/sessions/${sessionId}/features`, token)
}

export function getAnomalies(token: string, sessionId: number): Promise<AnomalyOut[]> {
  return request<AnomalyOut[]>(`/sessions/${sessionId}/anomalies`, token)
}

export function exportJson(token: string, sessionId: number): Promise<FeatureWindowExport[]> {
  return request<FeatureWindowExport[]>(`/sessions/${sessionId}/export.json`, token)
}

export async function exportCsv(token: string, sessionId: number): Promise<Blob> {
  const res = await fetch(`${API_BASE}/sessions/${sessionId}/export.csv`, {
    headers: { 'X-API-Token': token },
  })
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText)
    throw new ApiError(res.status, text)
  }
  return res.blob()
}

// ── Ingest ───────────────────────────────────────────────────────────────────

export function ingestBatch(token: string, batch: IngestBatch): Promise<IngestResponse> {
  return request<IngestResponse>('/ingest', token, {
    method: 'POST',
    body: JSON.stringify(batch),
  })
}

// ── Baseline recompute ────────────────────────────────────────────────────────

export function recomputeBaseline(token: string, horseId: number): Promise<unknown> {
  return request<unknown>(`/horses/${horseId}/baseline/recompute`, token, { method: 'POST' })
}

// ── Phase 7: Session trim ─────────────────────────────────────────────────────

export function updateTrim(token: string, sessionId: number, trim: TrimIn): Promise<TrimOut> {
  return request<TrimOut>(`/sessions/${sessionId}/trim`, token, {
    method: 'PATCH',
    body: JSON.stringify(trim),
  })
}
