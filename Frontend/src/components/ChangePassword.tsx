import { useState } from 'react'
import { KeyRound, X } from 'lucide-react'
import { api, errMessage, setToken } from '../api/client'
import type { TokenResponse } from '../api/types'
import { PasswordField } from './PasswordField'
import { useToast } from './Toast'

/** Change the signed-in account's password. Other sessions are ended server-side,
 *  so the new token returned here replaces the one this tab is holding. */
export function ChangePassword({ onClose }: { onClose: () => void }) {
  const toast = useToast()
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [confirm, setConfirm] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function submit() {
    setError('')
    if (next !== confirm) return setError('The two new passwords do not match.')
    if (next.length < 8) return setError('Your new password must be at least 8 characters.')
    if (next === current) return setError('Your new password must differ from the current one.')

    setBusy(true)
    try {
      const { data } = await api.post<TokenResponse>('/auth/change-password', {
        current_password: current,
        new_password: next,
      })
      setToken(data.access_token)  // the old sessions were just revoked
      toast({ title: 'Password changed', msg: 'You have been signed out on other devices.' })
      onClose()
    } catch (e) {
      setError(errMessage(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="modal-backdrop" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal sm">
        <div className="modal-header">
          <div className="file-icon doc"><KeyRound size={16} /></div>
          <div className="modal-title">Change password</div>
          <button className="modal-close" onClick={onClose} aria-label="Close"><X size={16} /></button>
        </div>

        <div className="modal-body">
          <PasswordField
            label="Current password"
            value={current}
            onChange={setCurrent}
            autoComplete="current-password"
            autoFocus
          />
          <PasswordField
            label="New password"
            value={next}
            onChange={setNext}
            autoComplete="new-password"
            strength
          />
          <PasswordField
            label="Confirm new password"
            value={confirm}
            onChange={setConfirm}
            autoComplete="new-password"
            matches={next}
            onEnter={submit}
          />
          <div className="field-hint">
            Changing your password signs you out everywhere else. This tab stays signed in.
          </div>
          {error && <div className="login-error" style={{ marginTop: 14 }}>{error}</div>}
        </div>

        <div className="modal-footer">
          <button className="btn ghost" onClick={onClose}>Cancel</button>
          <button className="btn primary" onClick={submit} disabled={busy}>
            {busy ? <span className="spinner" /> : <><KeyRound size={14} /> Change password</>}
          </button>
        </div>
      </div>
    </div>
  )
}
