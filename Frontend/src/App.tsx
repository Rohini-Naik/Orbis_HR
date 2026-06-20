import { AuthProvider, useAuth } from './auth/AuthContext'
import { ToastProvider } from './components/Toast'
import { LoginPage } from './pages/LoginPage'
import { EmployeeApp } from './pages/EmployeeApp'
import { AdminApp } from './pages/AdminApp'

function Root() {
  const { user, loading } = useAuth()
  if (loading) return <div className="center-screen"><span className="spinner" /> Loading…</div>
  if (!user) return <LoginPage />
  return user.role === 'admin' ? <AdminApp /> : <EmployeeApp />
}

export default function App() {
  return (
    <ToastProvider>
      <AuthProvider>
        <Root />
      </AuthProvider>
    </ToastProvider>
  )
}
