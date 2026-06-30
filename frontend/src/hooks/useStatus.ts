import { useState } from 'react'

export interface StatusState {
  message: string
  ok: boolean
}

export function useStatus() {
  const [status, setStatusState] = useState<StatusState>({ message: '', ok: true })

  function setStatus(message: string, ok = true) {
    setStatusState({ message, ok })
  }

  return { status, setStatus }
}
