import { useState } from 'react'
import { KeyRound, LogOut } from 'lucide-react'
import { useAuth } from '../auth/AuthContext'
import { BrandMark } from './Brand'
import { ChangePassword } from './ChangePassword'

function initials(name: string) {
  return name.split(' ').map((p) => p[0]).join('').slice(0, 2).toUpperCase()
}

export function TopNav() {
  const { user, logout } = useAuth()
  const [changing, setChanging] = useState(false)
  if (!user) return null
  const isAdmin = user.role === 'admin'

  return (
    <div className="top-nav">
      <div className="nav-brand">
        <BrandMark size={14} />
        Orbis
        <span className={`nav-role-badge ${user.role}`}>{isAdmin ? 'HR Admin' : 'Employee'}</span>
      </div>
      <div className="nav-spacer" />
      <div className="nav-status">
        <span className="status-dot" /> AI online
      </div>
      <div className="nav-user">
        <div className={`user-avatar ${isAdmin ? 'admin' : ''}`}>{initials(user.full_name)}</div>
        <div className="user-info">
          <div className="user-name">{user.full_name}</div>
          <div className="user-role">
            {user.department ?? (isAdmin ? 'Admin' : 'Employee')}
            {user.employee_id ? ` · ${user.employee_id}` : ''}
          </div>
        </div>
      </div>
      <button className="nav-logout" title="Change password" aria-label="Change password"
        onClick={() => setChanging(true)}>
        <KeyRound size={16} />
      </button>
      <button className="nav-logout" title="Sign out" aria-label="Sign out" onClick={logout}>
        <LogOut size={16} />
      </button>

      {changing && <ChangePassword onClose={() => setChanging(false)} />}
    </div>
  )
}
