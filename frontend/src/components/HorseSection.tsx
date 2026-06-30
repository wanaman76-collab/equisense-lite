import React from 'react'
import { btnStyle, inputStyle, sectionStyle } from './styles'

interface HorseSectionProps {
  token: string
  newHorseName: string
  onHorseNameChange: (value: string) => void
  onCreateHorse: () => void
}

export function HorseSection({ token, newHorseName, onHorseNameChange, onCreateHorse }: HorseSectionProps) {
  return (
    <div style={sectionStyle}>
      <h3 style={{ marginTop: 0 }}>Create Horse</h3>
      <label>Name</label>
      <input style={inputStyle} value={newHorseName} onChange={(e) => onHorseNameChange(e.target.value)} />
      <button style={btnStyle} onClick={onCreateHorse} disabled={!token}>
        Create Horse
      </button>
    </div>
  )
}
