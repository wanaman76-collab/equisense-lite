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

function Badge({ text, color }: { text: string, color: string }) {
  return (
    <span style={{
      display: 'inline-block',
      padding: '2px 8px',
      borderRadius: 999,
      background: color,
      color: '#111',
      fontSize: 12,
      border: '1px solid rgba(0,0,0,0.1)',
      marginLeft: 8,
      whiteSpace: 'nowrap',
    }}>
      {text}
    </span>
  )
}

function labelColor(label: string) {
  if (label === 'NORMAL') return '#d4edda'
  if (label === 'WATCH') return '#fff3cd'
  return '#f8d7da'
}

export default function App() {
  const { token, setToken } = useToken()
  const [horseId, setHorseId] = useState(1)
  const [newHorseName, setNewHorseName] = useState('Blaze')
  const [sessionId, setSessionId] = useState<number | undefined>()
  const [sessions, setSessions] = useState<any[]>([])
  const [selectedSessionId, setSelectedSessionId] = useState<number | undefined>()
  const [features, setFeatures] = useState<any[]>([])
  const [anomalies, setAnomalies] = useState<any[]>([])
  const [statusMsg, setStatusMsg] = useState('')
  const [statusOk, setStatusOk] = useState(true)
  const [computeResult, setComputeResult] = useState<any | null>(null)
  const [baselineBusySessionId, setBaselineBusySessionId] = useState<number | null>(null)
  const [baselineRecomputeBusy, setBaselineRecomputeBusy] = useState(false)

  const headers = { 'X-API-Token': token, 'Content-Type': 'application/json' }

  function setStatus(msg: string, ok = true) {
    setStatusMsg(msg); setStatusOk(ok)
  }

  async function createHorse() {
    try {
      const res = await fetch(`${API}/horses`, { method: 'POST', headers, body: JSON.stringify({ name: newHorseName }) })
      if (res.ok) setStatus(`Horse \