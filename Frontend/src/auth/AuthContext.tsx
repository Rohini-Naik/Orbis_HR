import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import { api, clearToken, getToken, setToken } from '../api/client'
import type { TokenResponse, UserProfile } from '../api/types'

interface AuthState {
  user: UserProfile | null
  loading: boolean
  login: (email: string, password: string) => Promise<UserProfile>
  /** Self-registration for staff already on the HR system. Identity is derived
   *  server-side from the company email — nothing else is sent. */
  signup: (email: string, password: string) => Promise<UserProfile>
  acceptInvite: (token: string, password: string) => Promise<UserProfile>
  logout: () => void
}

const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserProfile | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!getToken()) {
      setLoading(false)
      return
    }
    api
      .get<UserProfile>('/auth/me')
      .then((res) => setUser(res.data))
      .catch(() => clearToken())
      .finally(() => setLoading(false))
  }, [])

  async function afterAuth(token: string): Promise<UserProfile> {
    setToken(token)
    const me = await api.get<UserProfile>('/auth/me')
    setUser(me.data)
    return me.data
  }

  async function login(email: string, password: string) {
    const res = await api.post<TokenResponse>('/auth/login', { email, password })
    return afterAuth(res.data.access_token)
  }

  async function signup(email: string, password: string) {
    const res = await api.post<TokenResponse>('/auth/signup', { email, password })
    return afterAuth(res.data.access_token)
  }

  async function acceptInvite(token: string, password: string) {
    const res = await api.post<TokenResponse>('/auth/invite/accept', { token, password })
    return afterAuth(res.data.access_token)
  }

  function logout() {
    // Send the token explicitly: it is cleared before the interceptor would run.
    const token = getToken()
    clearToken()
    setUser(null)
    if (token) {
      api.post('/auth/logout', null, { headers: { Authorization: `Bearer ${token}` } })
        .catch(() => {})
    }
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, signup, acceptInvite, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
