import axios from 'axios'

const TOKEN_KEY = 'orbis_token'

export const getToken = () => localStorage.getItem(TOKEN_KEY)
export const setToken = (t: string) => localStorage.setItem(TOKEN_KEY, t)
export const clearToken = () => localStorage.removeItem(TOKEN_KEY)

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000',
})

// Attach the bearer token to every request.
api.interceptors.request.use((config) => {
  const token = getToken()
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// On 401 for an authenticated request (not the login/signup calls themselves),
// drop the stale token and reload so the app falls back to the login screen.
api.interceptors.response.use(
  (res) => res,
  (error) => {
    const url: string = error.config?.url ?? ''
    const isAuthCall = url.includes('/auth/login') || url.includes('/auth/signup')
    if (error.response?.status === 401 && !isAuthCall) {
      clearToken()
      location.reload()
    }
    return Promise.reject(error)
  },
)

/** Pull a human-readable message out of an Axios error. */
export function errMessage(e: unknown, fallback = 'Something went wrong'): string {
  if (axios.isAxiosError(e)) {
    const detail = e.response?.data?.detail
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail) && detail[0]?.msg) return detail[0].msg
    return e.message
  }
  return fallback
}
