import { useId, useState } from 'react'
import { Check, Eye, EyeOff } from 'lucide-react'

interface Props {
  label: string
  value: string
  onChange: (value: string) => void
  placeholder?: string
  autoComplete?: string
  onEnter?: () => void
  /** Show a strength meter — for fields where a password is being chosen. */
  strength?: boolean
  /** Compare against another field and confirm they match. */
  matches?: string
  autoFocus?: boolean
}

const MIN_LENGTH = 8

/** Rough guidance, not a gate: the server enforces the minimum length. */
function score(password: string): { level: number; label: string } {
  if (!password) return { level: 0, label: '' }
  let points = 0
  if (password.length >= MIN_LENGTH) points++
  if (password.length >= 12) points++
  if (/[a-z]/.test(password) && /[A-Z]/.test(password)) points++
  if (/\d/.test(password)) points++
  if (/[^A-Za-z0-9]/.test(password)) points++
  if (password.length < MIN_LENGTH) return { level: 1, label: `At least ${MIN_LENGTH} characters` }
  if (points <= 2) return { level: 1, label: 'Weak' }
  if (points === 3) return { level: 2, label: 'Fair' }
  if (points === 4) return { level: 3, label: 'Good' }
  return { level: 4, label: 'Strong' }
}

export function PasswordField({
  label, value, onChange, placeholder = '••••••••', autoComplete,
  onEnter, strength, matches, autoFocus,
}: Props) {
  const [visible, setVisible] = useState(false)
  const id = useId()
  const meter = strength ? score(value) : null
  const confirmed = matches !== undefined && value.length > 0 && value === matches

  return (
    <div className="field-group">
      <label className="field-label" htmlFor={id}>{label}</label>

      <div className="password-wrap">
        <input
          id={id}
          className="field-input"
          type={visible ? 'text' : 'password'}
          value={value}
          autoComplete={autoComplete}
          autoFocus={autoFocus}
          placeholder={placeholder}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter' && onEnter) onEnter() }}
        />
        {confirmed && <Check className="password-match" size={15} aria-hidden="true" />}
        <button
          type="button"
          className="password-toggle"
          onClick={() => setVisible((v) => !v)}
          aria-label={visible ? 'Hide password' : 'Show password'}
          title={visible ? 'Hide password' : 'Show password'}
          tabIndex={-1}
        >
          {visible ? <EyeOff size={16} /> : <Eye size={16} />}
        </button>
      </div>

      {meter && value.length > 0 && (
        <div className="pw-meter" aria-live="polite">
          <div className="pw-bars">
            {[1, 2, 3, 4].map((step) => (
              <span key={step} className={step <= meter.level ? `on lv${meter.level}` : ''} />
            ))}
          </div>
          <span className={`pw-label lv${meter.level}`}>{meter.label}</span>
        </div>
      )}
    </div>
  )
}
