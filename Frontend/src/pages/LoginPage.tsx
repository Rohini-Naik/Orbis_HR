import { useEffect, useState } from 'react'
import { ArrowRight, ArrowLeft, Info, KeyRound, MailCheck, ShieldCheck } from 'lucide-react'
import { useAuth } from '../auth/AuthContext'
import { BrandMark } from '../components/Brand'
import { PasswordField } from '../components/PasswordField'
import { api, errMessage } from '../api/client'
import type { InvitePreview, ResetPreview } from '../api/types'

type Mode = 'signin' | 'register' | 'invite' | 'forgot' | 'reset'

// Only ever an input hint; follows COMPANY_EMAIL_DOMAIN rather than being baked in.
const EMAIL_HINT = `you@${import.meta.env.VITE_COMPANY_EMAIL_DOMAIN ?? 'company.com'}`

/** New hires arrive as /?invite=…, reset links as /?reset=… */
function tokenFromUrl(key: 'invite' | 'reset'): string | null {
  return new URLSearchParams(window.location.search).get(key)
}

function clearUrl() {
  window.history.replaceState({}, '', window.location.pathname)
}

export function LoginPage() {
  const { login, signup, acceptInvite, resetPassword } = useAuth()

  const [mode, setMode] = useState<Mode>(() =>
    tokenFromUrl('invite') ? 'invite' : tokenFromUrl('reset') ? 'reset' : 'signin',
  )
  const [invite, setInvite] = useState<InvitePreview | null>(null)
  const [reset, setReset] = useState<ResetPreview | null>(null)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [sent, setSent] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  // Resolve whichever link brought the person here, so they can see which
  // account they are about to set a password for.
  useEffect(() => {
    const inviteToken = tokenFromUrl('invite')
    const resetToken = tokenFromUrl('reset')
    if (inviteToken) {
      api.get<InvitePreview>(`/auth/invite/${inviteToken}`)
        .then((r) => { setInvite(r.data); setEmail(r.data.company_email) })
        .catch((e) => {
          setError(errMessage(e, 'This invitation link is no longer valid.'))
          setMode('signin'); clearUrl()
        })
    } else if (resetToken) {
      api.get<ResetPreview>(`/auth/reset/${resetToken}`)
        .then((r) => { setReset(r.data); setEmail(r.data.email) })
        .catch((e) => {
          setError(errMessage(e, 'This reset link is no longer valid.'))
          setMode('signin'); clearUrl()
        })
    }
  }, [])

  function go(next: Mode) {
    setMode(next); setError(''); setSent(''); setPassword(''); setConfirm('')
  }

  const needsConfirm = mode === 'register' || mode === 'invite' || mode === 'reset'

  async function submit() {
    setError('')
    if (needsConfirm && password !== confirm) {
      setError('The two passwords do not match.')
      return
    }
    setBusy(true)
    try {
      if (mode === 'signin') {
        await login(email, password)
      } else if (mode === 'invite') {
        await acceptInvite(tokenFromUrl('invite')!, password)
        clearUrl()
      } else if (mode === 'reset') {
        await resetPassword(tokenFromUrl('reset')!, password)
        clearUrl()
      } else if (mode === 'forgot') {
        const { data } = await api.post<{ message: string }>('/auth/forgot-password', { email })
        setSent(data.message)
      } else {
        await signup(email, password)
      }
    } catch (e) {
      setError(errMessage(e, 'Something went wrong. Please try again.'))
    } finally {
      setBusy(false)
    }
  }

  const title = {
    signin: <>Sign in to your <em>compliance</em> workspace.</>,
    register: <>Activate your <em>employee</em> account.</>,
    invite: <>Welcome. Set your <em>password</em>.</>,
    forgot: <>Reset your <em>password</em>.</>,
    reset: <>Choose a <em>new password</em>.</>,
  }[mode]

  const subtitle = {
    signin: 'Your data stays on-premise.',
    register: 'Use the company address HR issued you.',
    invite: 'One step left before you can sign in.',
    forgot: "We'll email you a link to set a new one.",
    reset: 'This signs you out on every other device.',
  }[mode]

  const cta = {
    signin: 'Continue', register: 'Create account', invite: 'Create account',
    forgot: 'Send reset link', reset: 'Set new password',
  }[mode]

  return (
    <div className="login-view">
      <div className="login-brand">
        <BrandMark />
        <div className="brand-name">Orbis</div>
        <div className="brand-tag">HR Compliance Co-pilot</div>
      </div>

      <div className="login-card">
        <h1 className="login-title">{title}</h1>
        <p className="login-subtitle">{subtitle}</p>

        {mode === 'invite' && invite && (
          <div className="login-hint" style={{ marginBottom: 18 }}>
            <MailCheck size={14} style={{ verticalAlign: 'middle', marginRight: 6 }} />
            Hi <strong>{invite.full_name}</strong> — your company email is{' '}
            <code>{invite.company_email}</code>. Choose a password to finish setting up.
          </div>
        )}

        {mode === 'reset' && reset && (
          <div className="login-hint" style={{ marginBottom: 18 }}>
            <KeyRound size={14} style={{ verticalAlign: 'middle', marginRight: 6 }} />
            Resetting the password for <code>{reset.email}</code>.
          </div>
        )}

        {mode === 'register' && (
          <div className="login-hint" style={{ marginBottom: 18 }}>
            <Info size={14} style={{ verticalAlign: 'middle', marginRight: 6 }} />
            Use the company email address HR issued you. If it isn't recognised, contact HR.
          </div>
        )}

        {sent ? (
          <>
            <div className="login-sent">
              <MailCheck size={17} />
              <span>{sent}</span>
            </div>
            <div className="login-switch" style={{ marginTop: 18 }}>
              <button className="link-btn" onClick={() => go('signin')}>
                <ArrowLeft size={12} style={{ verticalAlign: 'middle', marginRight: 4 }} />
                Back to sign in
              </button>
            </div>
          </>
        ) : (
          <>
            <div className="field-group">
              <label className="field-label" htmlFor="login-email">Company email</label>
              <input
                id="login-email"
                className="field-input"
                type="email"
                value={email}
                autoComplete="username"
                disabled={mode === 'invite' || mode === 'reset'}
                onChange={(e) => setEmail(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter' && mode === 'forgot') submit() }}
                placeholder={EMAIL_HINT}
              />
            </div>

            {mode !== 'forgot' && (
              <PasswordField
                label={mode === 'signin' ? 'Password' : 'Choose a password'}
                value={password}
                onChange={setPassword}
                autoComplete={mode === 'signin' ? 'current-password' : 'new-password'}
                strength={mode !== 'signin'}
                onEnter={mode === 'signin' ? submit : undefined}
              />
            )}

            {needsConfirm && (
              <PasswordField
                label="Confirm password"
                value={confirm}
                onChange={setConfirm}
                autoComplete="new-password"
                matches={password}
                onEnter={submit}
              />
            )}

            {mode === 'signin' && (
              <div className="login-meta">
                <button className="link-btn" onClick={() => go('forgot')}>
                  Forgot your password?
                </button>
              </div>
            )}

            <button className="login-btn" onClick={submit} disabled={busy}>
              {busy ? <span className="spinner" /> : <>{cta} <ArrowRight size={16} /></>}
            </button>
          </>
        )}

        {error && <div className="login-error">{error}</div>}

        {!sent && mode !== 'invite' && mode !== 'reset' && (
          <div className="login-switch">
            {mode === 'signin' && (
              <>
                Already an employee?{' '}
                <button onClick={() => go('register')}>Activate your account</button>
              </>
            )}
            {mode === 'register' && (
              <>Already set up? <button onClick={() => go('signin')}>Sign in</button></>
            )}
            {mode === 'forgot' && (
              <button className="link-btn" onClick={() => go('signin')}>
                <ArrowLeft size={12} style={{ verticalAlign: 'middle', marginRight: 4 }} />
                Back to sign in
              </button>
            )}
          </div>
        )}

        {mode === 'reset' && (
          <div className="login-switch" style={{ fontSize: 11.5 }}>
            <ShieldCheck size={12} style={{ verticalAlign: 'middle', marginRight: 5 }} />
            Reset links expire and can only be used once.
          </div>
        )}
      </div>
    </div>
  )
}
