import React, { useState } from 'react'
import {
  computeSession,
  createHorse,
  exportCsv,
  getAnomalies,
  getFeatures,
  ingestBatch,
  listSessions,
  markBaseline,
  recomputeBaseline,
  startSession,
  stopSession,
} from './api/client'
import { ApiError } from './api/client'
import { ComputeReportSection } from './components/ComputeReportSection'
import { HorseSection } from './components/HorseSection'
import { LiveFeedPanel } from './components/LiveFeedPanel'
import { SessionControls } from './components/SessionControls'
import { SessionDetail } from './components/SessionDetail'
import { SessionsTable } from './components/SessionsTable'
import { StatusBar } from './components/UI'
import { TokenSection } from './components/TokenSection'
import { useStatus } from './hooks/useStatus'
import { useToken } from './hooks/useToken'
import type { AnomalyOut, ComputeResponse, FeatureWindowOut, SessionOut } from './types/api'

export default function App() {
  const { token, setToken } = useToken()
  const { status, setStatus } = useStatus()

  const [horseId, setHorseId] = useState(1)
  const [newHorseName, setNewHorseName] = useState('Blaze')
  const [sessionId, setSessionId] = useState<number | undefined>()
  const [sessions, setSessions] = useState<SessionOut[]>([])
  const [selectedSessionId, setSelectedSessionId] = useState<number | undefined>()
  const [features, setFeatures] = useState<FeatureWindowOut[]>([])
  const [anomalies, setAnomalies] = useState<AnomalyOut[]>([])
  const [computeResult, setComputeResult] = useState<ComputeResponse | null>(null)
  const [baselineBusySessionId, setBaselineBusySessionId] = useState<number | null>(null)
  const [baselineRecomputeBusy, setBaselineRecomputeBusy] = useState(false)
  const [demoBusy, setDemoBusy] = useState(false)
  const [demoLastSessionId, setDemoLastSessionId] = useState<number | null>(null)

  function handleError(e: unknown) {
    if (e instanceof ApiError) {
      setStatus(e.message, false)
    } else if (e instanceof Error) {
      setStatus(`Network error: ${e.message}`, false)
    } else {
      setStatus('Unknown error', false)
    }
  }

  async function handleCreateHorse() {
    try {
      await createHorse(token, newHorseName)
      setStatus(`Horse "${newHorseName}" created successfully.`)
    } catch (e) {
      handleError(e)
    }
  }

  async function handleStart() {
    try {
      const sess = await startSession(token, horseId, 'arena')
      setSessionId(sess.id)
      setComputeResult(null)
      setStatus(`Session #${sess.id} started.`)
    } catch (e) {
      handleError(e)
    }
  }

  async function handleIngestFake() {
    if (!sessionId) return
    try {
      const now = Date.now()
      const readings = Array.from({ length: 400 }, (_, i) => ({
        ts_ms: now + i * 50,
        ax: Math.sin(i / 5) / 10,
        ay: 0,
        az: Math.cos(i / 7) / 10,
        gx: 0.01,
        gy: 0.02,
        gz: 0.03,
      }))
      const result = await ingestBatch(token, { session_id: sessionId, readings })
      setStatus(`Fake readings ingested (${result.stored} samples).`)
    } catch (e) {
      handleError(e)
    }
  }

  async function handleCompute() {
    if (!sessionId) return
    try {
      const d = await computeSession(token, sessionId)
      setComputeResult(d)
      setStatus(
        `Computed ${d.windows} windows. Anomalies: ${d.anomalies_total} (med/high: ${d.anomalies_medium_high}). Overall: ${d.report.overall_label}.`,
      )
    } catch (e) {
      handleError(e)
    }
  }

  async function handleStop() {
    if (!sessionId) return
    try {
      await stopSession(token, sessionId)
      setStatus(`Session #${sessionId} stopped.`)
      setSessionId(undefined)
    } catch (e) {
      handleError(e)
    }
  }

  async function handleListSessions() {
    try {
      const data = await listSessions(token)
      setSessions(data)
      setStatus('Sessions refreshed.')
    } catch (e) {
      handleError(e)
    }
  }

  async function handleLoadSessionDetails(id: number) {
    setSelectedSessionId(id)
    try {
      const [feat, anoms] = await Promise.all([getFeatures(token, id), getAnomalies(token, id)])
      setFeatures(feat)
      setAnomalies(anoms)
      setStatus(`Loaded details for session #${id}.`)
    } catch (e) {
      handleError(e)
    }
  }

  async function handleMarkBaseline(id: number) {
    if (!token) return
    setBaselineBusySessionId(id)
    try {
      await markBaseline(token, id, true)
      setStatus(`Session #${id} marked as baseline ✓`)
      await handleListSessions()
    } catch (e) {
      handleError(e)
    } finally {
      setBaselineBusySessionId(null)
    }
  }

  async function handleRecomputeBaseline() {
    if (!token) return
    setBaselineRecomputeBusy(true)
    try {
      await recomputeBaseline(token, horseId)
      setStatus(`Baseline recomputed for horse #${horseId} ✓`)
    } catch (e) {
      handleError(e)
    } finally {
      setBaselineRecomputeBusy(false)
    }
  }

  async function handleExportCsv(id: number) {
    try {
      const blob = await exportCsv(token, id)
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `session_${id}_windows.csv`
      document.body.appendChild(a)
      a.click()
      a.remove()
      URL.revokeObjectURL(url)
      setStatus(`Downloaded CSV export for session #${id}.`)
    } catch (e) {
      handleError(e)
    }
  }

  async function handleRunDemo() {
    if (!token) return
    setDemoBusy(true)
    try {
      const sess = await startSession(token, horseId, 'arena')
      const sid = sess.id
      setSessionId(sid)
      setDemoLastSessionId(sid)
      setComputeResult(null)
      setSelectedSessionId(undefined)
      setFeatures([])
      setAnomalies([])
      setStatus(`Demo started session #${sid}. Ingesting + computing…`)

      const now = Date.now()
      const readings = Array.from({ length: 400 }, (_, i) => ({
        ts_ms: now + i * 50,
        ax: Math.sin(i / 5) / 10,
        ay: 0,
        az: Math.cos(i / 7) / 10,
        gx: 0.01,
        gy: 0.02,
        gz: 0.03,
      }))
      await ingestBatch(token, { session_id: sid, readings })

      const compData = await computeSession(token, sid)
      setComputeResult(compData)

      await handleListSessions()
      await handleLoadSessionDetails(sid)

      setStatus(
        `Demo complete ✓ Session #${sid}: ${compData.report.overall_label} with ${compData.anomalies_total} anomalies.`,
      )
    } catch (e) {
      handleError(e)
    } finally {
      setDemoBusy(false)
    }
  }

  return (
    <div style={{ padding: 16, fontFamily: 'sans-serif', maxWidth: 760, margin: '0 auto' }}>
      <h2 style={{ marginTop: 0 }}>EquiSense Lite</h2>

      <StatusBar status={status} />

      <TokenSection token={token} onTokenChange={setToken} />

      <HorseSection
        token={token}
        newHorseName={newHorseName}
        onHorseNameChange={setNewHorseName}
        onCreateHorse={handleCreateHorse}
      />

      <SessionControls
        token={token}
        horseId={horseId}
        sessionId={sessionId}
        demoBusy={demoBusy}
        baselineRecomputeBusy={baselineRecomputeBusy}
        onHorseIdChange={setHorseId}
        onStart={handleStart}
        onIngestFake={handleIngestFake}
        onCompute={handleCompute}
        onStop={handleStop}
        onRunDemo={handleRunDemo}
        onRecomputeBaseline={handleRecomputeBaseline}
      />

      {sessionId !== undefined && (
        <LiveFeedPanel sessionId={sessionId} token={token} />
      )}

      {computeResult && (
        <ComputeReportSection
          computeResult={computeResult}
          anomalies={anomalies}
          demoLastSessionId={demoLastSessionId}
          onExportCsv={handleExportCsv}
        />
      )}

      <SessionsTable
        token={token}
        sessions={sessions}
        selectedSessionId={selectedSessionId}
        baselineBusySessionId={baselineBusySessionId}
        onRefresh={handleListSessions}
        onViewSession={handleLoadSessionDetails}
        onMarkBaseline={handleMarkBaseline}
      />

      {selectedSessionId !== undefined && (
        <SessionDetail sessionId={selectedSessionId} features={features} anomalies={anomalies} />
      )}
    </div>
  )
}
