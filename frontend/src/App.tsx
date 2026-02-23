import React, { useState, useEffect } from 'react'
const API = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'
const tokenKey = 'api_token'

function useToken() {
  const [token, setToken] = useState(localStorage.getItem(tokenKey) || '')
  useEffect(() => { if (token) localStorage.setItem(tokenKey, token) }, [token])
  return { token, setToken }
}

const sectionStyle: React.CSSProperties = {
  marginBottom: 24,
  padding: '16px',
  border: '1px solid #ddd',
  borderRadius: 8,
}

const btnStyle: React.CSSProperties = {
  padding: '10px 18px',
  fontSize: 16,
  marginRight: 8,
  marginTop: 6,
  borderRadius: 6,
  cursor: 'pointer',
  border: '1px solid #aaa',
}

const inputStyle: React.CSSProperties = {
  padding: '8px 10px',
  fontSize: 16,
  borderRadius: 6,
  border: '1px solid #aaa',
  width: '100%',
  boxSizing: 'border-box',
  marginTop: 4,
}

const tableStyle: React.CSSProperties = {
  width: '100%',
  borderCollapse: 'collapse',
  fontSize: 13,
  overflowX: 'auto',
  display: 'block',
}

const thStyle: React.CSSProperties = { border: '1px solid #ccc', padding: '4px 8px', background: '#f5f5f5', whiteSpace: 'nowrap' }
const tdStyle: React.CSSProperties = { border: '1px solid #ccc', padding: '4px 8px', whiteSpace: 'nowrap' }

export default function App() {
  const { token, setToken } = useToken()
  const [horseId, setHorseId] = useState(1)
  const [newHorseName, setNewHorseName] = useState('Blaze')
  const [sessionId, setSessionId] = useState<number|undefined>()
  const [sessions, setSessions] = useState<any[]>([])
  const [selectedSessionId, setSelectedSessionId] = useState<number|undefined>()
  const [features, setFeatures] = useState<any[]>([])
  const [anomalies, setAnomalies] = useState<any[]>([])
  const [statusMsg, setStatusMsg] = useState('')
  const [statusOk, setStatusOk] = useState(true)
  const headers = { 'X-API-Token': token, 'Content-Type': 'application/json' }

  function setStatus(msg: string, ok = true) {
    setStatusMsg(msg); setStatusOk(ok)
  }

  async function createHorse() {
    try {
      const res = await fetch(`${API}/horses`, { method:'POST', headers, body: JSON.stringify({ name: newHorseName }) })
      if (res.ok) setStatus(`Horse "${newHorseName}" created successfully.`)
      else {
        const body = await res.json().catch(() => ({}))
        setStatus(`Failed to create horse: ${body.detail ?? res.statusText}`, false)
      }
    } catch (e: any) {
      setStatus(`Network error: ${e.message}`, false)
    }
  }

  async function start() {
    try {
      const res = await fetch(`${API}/sessions`, { method:'POST', headers, body: JSON.stringify({ horse_id: horseId, surface:'arena' }) })
      if (res.ok) {
        const data = await res.json()
        setSessionId(data.id)
        setStatus(`Session #${data.id} started.`)
      } else {
        const body = await res.json().catch(() => ({}))
        setStatus(`Failed to start session: ${body.detail ?? res.statusText}`, false)
      }
    } catch (e: any) {
      setStatus(`Network error: ${e.message}`, false)
    }
  }

  async function ingestFake() {
    if (!sessionId) return
    try {
      const now = Date.now()
      const readings = Array.from({length:400}, (_,i)=>({ ts_ms: now + i*50, ax: Math.sin(i/5)/10, ay: 0, az: Math.cos(i/7)/10, gx:0.01, gy:0.02, gz:0.03 }))
      const res = await fetch(`${API}/ingest`, { method:'POST', headers, body: JSON.stringify({ session_id: sessionId, readings }) })
      if (res.ok) setStatus('Fake readings ingested (400 samples).')
      else setStatus(`Ingest failed: ${res.statusText}`, false)
    } catch (e: any) {
      setStatus(`Network error: ${e.message}`, false)
    }
  }

  async function compute() {
    if (!sessionId) return
    try {
      const res = await fetch(`${API}/sessions/${sessionId}/compute`, { method:'POST', headers })
      if (res.ok) {
        const d = await res.json()
        setStatus(`Computed ${d.windows} windows, ${d.anomalies} anomalies.`)
      } else setStatus(`Compute failed: ${res.statusText}`, false)
    } catch (e: any) {
      setStatus(`Network error: ${e.message}`, false)
    }
  }

  async function stop() {
    if (!sessionId) return
    try {
      const res = await fetch(`${API}/sessions/${sessionId}/stop`, { method:'POST', headers })
      if (res.ok) {
        setStatus(`Session #${sessionId} stopped.`)
        setSessionId(undefined)
      } else setStatus(`Stop failed: ${res.statusText}`, false)
    } catch (e: any) {
      setStatus(`Network error: ${e.message}`, false)
    }
  }

  async function listSessions() {
    try {
      const res = await fetch(`${API}/sessions`, { headers })
      if (res.ok) {
        setSessions(await res.json())
        setStatus('Sessions refreshed.')
      } else setStatus(`Failed to list sessions: ${res.statusText}`, false)
    } catch (e: any) {
      setStatus(`Network error: ${e.message}`, false)
    }
  }

  async function loadSessionDetails(id: number) {
    setSelectedSessionId(id)
    try {
      const [fr, ar] = await Promise.all([
        fetch(`${API}/sessions/${id}/features`, { headers }),
        fetch(`${API}/sessions/${id}/anomalies`, { headers }),
      ])
      setFeatures(fr.ok ? await fr.json() : [])
      setAnomalies(ar.ok ? await ar.json() : [])
      setStatus(`Loaded details for session #${id}.`)
    } catch (e: any) {
      setStatus(`Network error: ${e.message}`, false)
    }
  }

  return (
    <div style={{padding:16, fontFamily:'sans-serif', maxWidth:600, margin:'0 auto'}}>
      <h2 style={{marginTop:0}}>EquiSense Lite</h2>

      {statusMsg && (
        <div style={{
          padding:'10px 14px', borderRadius:6, marginBottom:16,
          background: statusOk ? '#e6f4ea' : '#fce8e6',
          color: statusOk ? '#1e7e34' : '#c0392b',
          border: `1px solid ${statusOk ? '#a8d5b0' : '#f1a9a0'}`,
        }}>
          {statusMsg}
        </div>
      )}

      <div style={sectionStyle}>
        <h3 style={{marginTop:0}}>API Token</h3>
        <input style={inputStyle} placeholder="X-API-Token (e.g. dev-token)" value={token} onChange={e=>setToken(e.target.value)} />
        <small style={{color:'#666'}}>Stored in localStorage. Use "dev-token" for local dev.</small>
      </div>

      <div style={sectionStyle}>
        <h3 style={{marginTop:0}}>Create Horse</h3>
        <label>Name</label>
        <input style={inputStyle} value={newHorseName} onChange={e=>setNewHorseName(e.target.value)} />
        <button style={btnStyle} onClick={createHorse} disabled={!token}>Create Horse</button>
      </div>

      <div style={sectionStyle}>
        <h3 style={{marginTop:0}}>Session Controls</h3>
        <label>Horse ID</label>
        <input style={{...inputStyle, width:80}} type="number" value={horseId} onChange={e=>setHorseId(parseInt(e.target.value))} />
        <div style={{marginTop:10, display:'flex', flexWrap:'wrap', gap:8}}>
          <button style={btnStyle} onClick={start} disabled={!token}>Start Session</button>
          <button style={btnStyle} onClick={ingestFake} disabled={!sessionId}>Ingest Fake Data</button>
          <button style={btnStyle} onClick={compute} disabled={!sessionId}>Compute</button>
          <button style={btnStyle} onClick={stop} disabled={!sessionId}>Stop Session</button>
        </div>
        {sessionId && <p style={{color:'#555', marginBottom:0}}>Active session: <strong>#{sessionId}</strong></p>}
      </div>

      <div style={sectionStyle}>
        <h3 style={{marginTop:0}}>Sessions</h3>
        <button style={btnStyle} onClick={listSessions} disabled={!token}>Refresh</button>
        {sessions.length > 0 && (
          <table style={tableStyle}>
            <thead>
              <tr>
                <th style={thStyle}>#</th>
                <th style={thStyle}>Status</th>
                <th style={thStyle}>Started</th>
                <th style={thStyle}>Details</th>
              </tr>
            </thead>
            <tbody>
              {sessions.map(s => (
                <tr key={s.id} style={{background: selectedSessionId===s.id ? '#fffde7':undefined}}>
                  <td style={tdStyle}>{s.id}</td>
                  <td style={tdStyle}>{s.status}</td>
                  <td style={tdStyle}>{new Date(s.started_at).toLocaleString()}</td>
                  <td style={tdStyle}>
                    <button style={{...btnStyle, padding:'4px 10px', fontSize:13, marginTop:0}} onClick={()=>loadSessionDetails(s.id)}>View</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {selectedSessionId !== undefined && (
        <>
          <div style={sectionStyle}>
            <h3 style={{marginTop:0}}>Feature Windows — Session #{selectedSessionId}</h3>
            {features.length === 0 ? <p style={{color:'#999'}}>No features computed yet.</p> : (
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
                  {features.map((f: any) => (
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
            <h3 style={{marginTop:0}}>Anomalies — Session #{selectedSessionId}</h3>
            {anomalies.length === 0 ? <p style={{color:'#999'}}>No anomalies detected.</p> : (
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
                  {anomalies.map((a: any) => (
                    <tr key={a.id}>
                      <td style={tdStyle}>{a.id}</td>
                      <td style={tdStyle}>{a.severity}</td>
                      <td style={tdStyle}>{a.score?.toFixed(3)}</td>
                      <td style={tdStyle}>{a.method}</td>
                      <td style={tdStyle}>{new Date(a.created_at).toLocaleString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </>
      )}
    </div>
  )
}

