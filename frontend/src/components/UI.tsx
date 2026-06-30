import React from 'react'
import type { StatusState } from '../hooks/useStatus'

export function Badge({ text, color }: { text: string; color: string }) {
  return (
    <span
      style={{
        display: 'inline-block',
        padding: '2px 8px',
        borderRadius: 999,
        background: color,
        color: '#111',
        fontSize: 12,
        border: '1px solid rgba(0,0,0,0.1)',
        marginLeft: 8,
        whiteSpace: 'nowrap',
      }}
    >
      {text}
    </span>
  )
}

export function StatusBar({ status }: { status: StatusState }) {
  if (!status.message) return null
  return (
    <div
      style={{
        padding: '10px 14px',
        borderRadius: 6,
        marginBottom: 16,
        background: status.ok ? '#e6f4ea' : '#fce8e6',
        color: status.ok ? '#1e7e34' : '#c0392b',
        border: `1px solid ${status.ok ? '#a8d5b0' : '#f1a9a0'}`,
      }}
    >
      {status.message}
    </div>
  )
}

export function labelColor(label: string): string {
  if (label === 'NORMAL') return '#d4edda'
  if (label === 'WATCH') return '#fff3cd'
  return '#f8d7da'
}
