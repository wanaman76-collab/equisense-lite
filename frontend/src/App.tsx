import React, { useState, useEffect } from 'react'
const API = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'
const tokenKey = 'api_token'

function useToken() {
  const [token, setToken] = useState(localStorage.getItem(tokenKey) || '')
  useEffect(() => { if (token) localStorage.setItem(tokenKey, token) }, [token])
  return { token, setToken }
}

export default function App() {
  const { token, setToken } = useToken()
  const [horseId, setHorseId] = useState(1)
  const [newHorseName, setNewHorseName] = useState('Blaze')
  const [sessionId, setSessionId] = useState<number|undefined>()
  const [sessions, setSessions] = useState<any[]>([])
  const headers = { 'X-API-Token': token, 'Content-Type': 'application/json' }

  async function createHorse() {
    const res = await fetch(`${API}/horses`, { method:'POST', headers, body: JSON.stringify({ name: newHorseName }) })
    if (res.ok) alert('Horse created'); else alert('Failed: ' + (await res.text()))
  }
  async function start() {
    const res = await fetch(`${API}/sessions`, { method:'POST', headers, body: JSON.stringify({ horse_id: horseId, surface:'arena' }) })
    const data = await res.json()
    setSessionId(data.id)
  }
  async function ingestFake() {
    if (!sessionId) return
    const now = Date.now()
    const readings = Array.from({length:400}, (_,i)=>({ ts_ms: now + i*50, ax: Math.sin(i/5)/10, ay: 0, az: Math.cos(i/7)/10, gx:0.01, gy:0.02, gz:0.03 }))
    await fetch(`${API}/ingest`, { method:'POST', headers, body: JSON.stringify({ session_id: sessionId, readings }) })
  }
  async function compute() {
    if (!sessionId) return
    await fetch(`${API}/sessions/${sessionId}/compute`, { method:'POST', headers })
  }
  async function stop() {
    if (!sessionId) return
    await fetch(`${API}/sessions/${sessionId}/stop`, { method:'POST', headers })
    setSessionId(undefined)
  }
  async function listSessions() {
    const res = await fetch(`${API}/sessions`, { headers })
    setSessions(await res.json())
  }

  return (
    <div style={{padding:20, fontFamily:'sans-serif'}}>
      <h2>EquiSense Lite</h2>
      <div style={{display:'flex', gap:16}}>
        <div>
          <h3>Token</h3>
          <input placeholder="X-API-Token" value={token} onChange={e=>setToken(e.target.value)} />
        </div>
        <div>
          <h3>Horse</h3>
          <div>Horse ID: <input type="number" value={horseId} onChange={e=>setHorseId(parseInt(e.target.value))} /></div>
          <div>Create: <input value={newHorseName} onChange={e=>setNewHorseName(e.target.value)} />
            <button onClick={createHorse} disabled={!token}>Create Horse</button>
          </div>
        </div>
        <div>
          <h3>Session</h3>
          <button onClick={start} disabled={!token}>Start</button>
          <button onClick={ingestFake} disabled={!sessionId}>Ingest Fake</button>
          <button onClick={compute} disabled={!sessionId}>Compute</button>
          <button onClick={stop} disabled={!sessionId}>Stop</button>
        </div>
        <div>
          <h3>Sessions</h3>
          <button onClick={listSessions} disabled={!token}>Refresh</button>
          <ul>
            {sessions.map(s => <li key={s.id}>#{s.id} {s.status} started {new Date(s.started_at).toLocaleString()}</li>)}
          </ul>
        </div>
      </div>
      <p style={{marginTop:20, color:'#666'}}>Tip: use token value like "dev" to pass the simple middleware.</p>
    </div>
  )
}
