import { describe, it, expect } from 'vitest'
import { render } from '@testing-library/react'
import React from 'react'
import App from './App'

describe('App', () => {
  it('renders title', () => {
    const { getByText } = render(<App />)
    expect(getByText(/EquiSense Lite/i)).toBeTruthy()
  })

  it('renders watch existing session controls', () => {
    const { getAllByText, getAllByPlaceholderText } = render(<App />)
    expect(getAllByText(/Watch Session ID/i).length).toBeGreaterThan(0)
    expect(getAllByPlaceholderText(/Session ID/i).length).toBeGreaterThan(0)
  })
})
