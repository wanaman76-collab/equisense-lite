import { useEffect, useState } from 'react'

const TOKEN_KEY = 'api_token'

// sessionStorage is used intentionally: the token is only kept for the current
// browser session and is cleared when the tab/window is closed.  This is safer
// than localStorage because the credential does not persist across sessions,
// reducing the exposure window if a device is shared or borrowed.
export function useToken() {
  const [token, setTokenState] = useState<string>(sessionStorage.getItem(TOKEN_KEY) ?? '')

  useEffect(() => {
    if (token) {
      sessionStorage.setItem(TOKEN_KEY, token)
    }
  }, [token])

  return { token, setToken: setTokenState }
}
