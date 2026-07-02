import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render } from '@testing-library/react'
import React from 'react'
import App from './App'

beforeEach(() => {
  vi.stubGlobal(
    'WebSocket',
    class {
      url: string
      onopen: (() => void) | null = null
      onmessage: ((e: { data: string }) => void) | null = null
      onerror: (() => void) | null = null
      onclose: (() => void) | null = null
      constructor(url: string) {
        this.url = url
      }
      close() {}
    },
  )
})

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

  it('lets user watch a manually entered session id', () => {
    const { getAllByPlaceholderText, getAllByText } = render(<App />)
    fireEvent.change(getAllByPlaceholderText(/X-API-Token/i)[0], { target: { value: 'dev-token' } })
    fireEvent.change(getAllByPlaceholderText(/Session ID/i)[0], { target: { value: '7' } })
    fireEvent.click(getAllByText(/Watch Session ID/i)[0])
    expect(getAllByText(/Watching live session:/i).length).toBeGreaterThan(0)
    expect(getAllByText(/Live Feed — Session #7/i).length).toBeGreaterThan(0)
  })
})
