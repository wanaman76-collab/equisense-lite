import React from 'react'
import { btnStyle, inputStyle, sectionStyle } from './styles'

interface TokenSectionProps {
  token: string
  onTokenChange: (value: string) => void
}

export function TokenSection({ token, onTokenChange }: TokenSectionProps) {
  return (
    <div style={sectionStyle}>
      <h3 style={{ marginTop: 0 }}>API Token</h3>
      <input
        style={inputStyle}
        placeholder="X-API-Token (e.g. dev-token)"
        value={token}
        onChange={(e) => onTokenChange(e.target.value)}
      />
      <small style={{ color: '#666' }}>Stored in localStorage. Use &ldquo;dev-token&rdquo; for local dev.</small>
    </div>
  )
}
