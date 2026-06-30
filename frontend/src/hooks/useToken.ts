import { useEffect, useState } from 'react'

const TOKEN_KEY = 'api_token'

export function useToken() {
  const [token, setTokenState] = useState<string>(localStorage.getItem(TOKEN_KEY) ?? '')

  useEffect(() => {
    if (token) {
      localStorage.setItem(TOKEN_KEY, token)
    }
  }, [token])

  return { token, setToken: setTokenState }
}
