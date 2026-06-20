import { useState } from 'react'
import { ArrowRight, Info, ShieldCheck, UserRound } from 'lucide-react'
import { useAuth } from '../auth/AuthContext'
import { BrandMark } from '../components/Brand'
import { errMessage } from '../api/client'

const DEMO = {
  employee: { email: 'priya.sharma@acmecorp.com', password: 'demo1234' },
  admin: { email: 'rohit.verma@acmecorp.com', password: 'demo1234' },
}

export function LoginPage() {
  const { login, signup } = useAuth()
  const [mode, setMode] = useState<'signin' | 'signup'>('signin')
  const [demoRole, setDemoRole] = useState<'employee' | 'admin'>('employee')
  const [email, setEmail] = useState(DEMO.employee.email)
  const [password, setPassword] = useState(DEMO.employee.password)
  const [fullName, setFullName] = useState('')
  const [employeeId, setEmployeeId] = useState('')
  const [department, setDepartment] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  function pickRole(role: 'employee' | 'admin') {
    setDemoRole(role)
    setEmail(DEMO[role].email)
    setPassword(DEMO[role].password)
  }

  async function submit() {
    setError('')
    setBusy(true)
    try {
      if (mode === 'signin') {
        await login(email, password)
      } else {
        await signup({
          email,
          password,
          full_name: fullName,
          employee_id: employeeId ? Number(employeeId) : null,
          department: department || null,
        })
      }
    } catch (e) {
      setError(errMessage(e, 'Authentication failed'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="login-view">
      <div className="login-brand">
        <BrandMark />
        <div className="brand-name">Orbis</div>
        <div className="brand-tag">HR Compliance Co-pilot</div>
      </div>

      <div className="login-card">
        <h1 className="login-title">
          {mode === 'signin' ? (
            <>Sign in to your <em>compliance</em> workspace.</>
          ) : (
            <>Create your <em>employee</em> account.</>
          )}
        </h1>
        <p className="login-subtitle">Your data stays on-premise.</p>

        {mode === 'signin' && (
          <div className="role-toggle">
            <button className={`role-btn employee ${demoRole === 'employee' ? 'active' : ''}`} onClick={() => pickRole('employee')}>
              <UserRound size={15} /> Employee
            </button>
            <button className={`role-btn admin ${demoRole === 'admin' ? 'active' : ''}`} onClick={() => pickRole('admin')}>
              <ShieldCheck size={15} /> HR Admin
            </button>
          </div>
        )}

        {mode === 'signup' && (
          <>
            <div className="field-group">
              <label className="field-label">Full name</label>
              <input className="field-input" value={fullName} onChange={(e) => setFullName(e.target.value)} placeholder="Jane Doe" />
            </div>
            <div className="field-group">
              <label className="field-label">Employee ID (for personal data access)</label>
              <input className="field-input" value={employeeId} onChange={(e) => setEmployeeId(e.target.value)} placeholder="2001" />
            </div>
            <div className="field-group">
              <label className="field-label">Department</label>
              <input className="field-input" value={department} onChange={(e) => setDepartment(e.target.value)} placeholder="Engineering" />
            </div>
          </>
        )}

        <div className="field-group">
          <label className="field-label">Work email</label>
          <input className="field-input" type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@company.com" />
        </div>
        <div className="field-group">
          <label className="field-label">Password</label>
          <input className="field-input" type="password" value={password} onChange={(e) => setPassword(e.target.value)}
            placeholder="••••••••" onKeyDown={(e) => e.key === 'Enter' && submit()} />
        </div>

        <button className="login-btn" onClick={submit} disabled={busy}>
          {busy ? <span className="spinner" /> : <>{mode === 'signin' ? 'Continue' : 'Create account'} <ArrowRight size={16} /></>}
        </button>

        {error && <div className="login-error">{error}</div>}

        {mode === 'signin' && (
          <div className="login-hint">
            <Info size={14} style={{ verticalAlign: 'middle', marginRight: 6 }} />
            <strong>Demo</strong> — toggle <code>Employee</code> ↔ <code>Admin</code> to autofill credentials.
          </div>
        )}

        <div className="login-switch">
          {mode === 'signin' ? (
            <>New employee? <button onClick={() => { setMode('signup'); setError('') }}>Create an account</button></>
          ) : (
            <>Already have an account? <button onClick={() => { setMode('signin'); setError('') }}>Sign in</button></>
          )}
        </div>
      </div>
    </div>
  )
}
