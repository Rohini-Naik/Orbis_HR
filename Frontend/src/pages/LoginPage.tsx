import { useEffect, useState } from 'react'
import { ArrowRight, Info, MailCheck } from 'lucide-react'
import { useAuth } from '../auth/AuthContext'
import { BrandMark } from '../components/Brand'
import { api, errMessage } from '../api/client'
import type { InvitePreview } from '../api/types'

type Mode = 'signin' | 'register' | 'invite'

// Only ever used as an input hint. Kept in config so it follows
// COMPANY_EMAIL_DOMAIN rather than being baked into the page.
const EMAIL_HINT = `you@${import.meta.env.VITE_COMPANY_EMAIL_DOMAIN ?? 'company.com'}`

/** New hires arrive from their invitation email as /?invite=<token>. */
function inviteTokenFromUrl(): string | null {
  return new URLSearchParams(window.location.search).get('invite')
}

export function LoginPage() {
  const { login, signup, acceptInvite } = useAuth()
  const [mode, setMode] = useState<Mode>(() => (inviteTokenFromUrl() ? 'invite' : 'signin'))
  const [invite, setInvite] = useState<InvitePreview | null>(null)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  // Resolve the invitation so the new hire sees the address being created.
  useEffect(() => {
    const token = inviteTokenFromUrl()
    if (!token) return
    api
      .get<InvitePreview>(`/auth/invite/${token}`)
      .then((r) => {
        setInvite(r.data)
        setEmail(r.data.company_email)
      })
      .catch((e) => {
        setError(errMessage(e, 'This invitation link is no longer valid.'))
        setMode('signin')
      })
  }, [])

  async function submit() {
    setError('')
    if (mode !== 'signin' && password !== confirm) {
      setError('Passwords do not match.')
      return
    }
    setBusy(true)
    try {
      if (mode === 'signin') {
        await login(email, password)
      } else if (mode === 'invite') {
        await acceptInvite(inviteTokenFromUrl()!, password)
        window.history.replaceState({}, '', window.location.pathname)
      } else {
        await signup(email, password)
      }
    } catch (e) {
      setError(errMessage(e, 'Authentication failed'))
    } finally {
      setBusy(false)
    }
  }

  const title =
    mode === 'signin' ? (
      <>Sign in to your <em>compliance</em> workspace.</>
    ) : mode === 'invite' ? (
      <>Welcome. Set your <em>password</em>.</>
    ) : (
      <>Activate your <em>employee</em> account.</>
    )

  return (
    <div className="login-view">
      <div className="login-brand">
        <BrandMark />
        <div className="brand-name">Orbis</div>
        <div className="brand-tag">HR Compliance Co-pilot</div>
      </div>

      <div className="login-card">
        <h1 className="login-title">{title}</h1>
        <p className="login-subtitle">Your data stays on-premise.</p>

        {mode === 'invite' && invite && (
          <div className="login-hint" style={{ marginBottom: 18 }}>
            <MailCheck size={14} style={{ verticalAlign: 'middle', marginRight: 6 }} />
            Hi <strong>{invite.full_name}</strong> — your company email is{' '}
            <code>{invite.company_email}</code>. Choose a password to finish setting up.
          </div>
        )}

        {mode === 'register' && (
          <div className="login-hint" style={{ marginBottom: 18 }}>
            <Info size={14} style={{ verticalAlign: 'middle', marginRight: 6 }} />
            Use the company email address HR issued you. If it isn't recognised, contact HR.
          </div>
        )}

        <div className="field-group">
          <label className="field-label">Company email</label>
          <input
            className="field-input"
            type="email"
            value={email}
            disabled={mode === 'invite'}
            onChange={(e) => setEmail(e.target.value)}
            placeholder={EMAIL_HINT}
          />
        </div>

        <div className="field-group">
          <label className="field-label">{mode === 'signin' ? 'Password' : 'Choose a password'}</label>
          <input
            className="field-input"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="••••••••"
            onKeyDown={(e) => e.key === 'Enter' && mode === 'signin' && submit()}
          />
        </div>

        {mode !== 'signin' && (
          <div className="field-group">
            <label className="field-label">Confirm password</label>
            <input
              className="field-input"
              type="password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              placeholder="••••••••"
              onKeyDown={(e) => e.key === 'Enter' && submit()}
            />
          </div>
        )}

        <button className="login-btn" onClick={submit} disabled={busy}>
          {busy ? (
            <span className="spinner" />
          ) : (
            <>
              {mode === 'signin' ? 'Continue' : 'Create account'} <ArrowRight size={16} />
            </>
          )}
        </button>

        {error && <div className="login-error">{error}</div>}

        {mode !== 'invite' && (
          <div className="login-switch">
            {mode === 'signin' ? (
              <>
                Already an employee?{' '}
                <button onClick={() => { setMode('register'); setError('') }}>
                  Activate your account
                </button>
              </>
            ) : (
              <>
                Already set up?{' '}
                <button onClick={() => { setMode('signin'); setError('') }}>Sign in</button>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
