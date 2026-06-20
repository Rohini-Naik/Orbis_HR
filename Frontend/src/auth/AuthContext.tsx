import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import { api, clearToken, getToken, setToken } from '../api/client'
import type { TokenResponse, UserProfile } from '../api/types'

interface SignupPayload {
  email: string
  password: string
  full_name: string
  employee_id?: number | null
  department?: string | null
}

interface AuthState {
  user: UserProfile | null
  loading: boolean
  login: (email: string, password: string) => Promise<UserProfile>
  signup: (payload: SignupPayload) => Promise<UserProfile>
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

  async function signup(payload: SignupPayload) {
    const res = await api.post<TokenResponse>('/auth/signup', payload)
    return afterAuth(res.data.access_token)
  }

  function logout() {
    clearToken()
    setUser(null)
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, signup, logout }}>
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
