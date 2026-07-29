import { useEffect, useState } from 'react'
import { ShieldCheck, ShieldOff, UserRound } from 'lucide-react'
import { api, errMessage } from '../../api/client'
import type { UserSummary } from '../../api/types'
import { useAuth } from '../../auth/AuthContext'
import { useToast } from '../../components/Toast'

const GRID = '1fr 220px 120px 110px 150px'

export function UserAdmin() {
  const toast = useToast()
  const { user: me } = useAuth()
  const [users, setUsers] = useState<UserSummary[]>([])
  const [busy, setBusy] = useState<number | null>(null)

  useEffect(() => { load() }, [])

  function load() {
    api.get<UserSummary[]>('/users').then((r) => setUsers(r.data)).catch(() => {})
  }

  async function setRole(u: UserSummary, role: 'admin' | 'employee') {
    const verb = role === 'admin' ? 'Grant admin access to' : 'Revoke admin access from'
    if (!confirm(`${verb} ${u.full_name}? They will be signed out and must sign in again.`)) return
    setBusy(u.id)
    try {
      await api.put(`/users/${u.id}/role`, { role })
      toast({
        title: role === 'admin' ? 'Admin access granted' : 'Admin access revoked',
        msg: `${u.full_name} is now ${role === 'admin' ? 'an HR admin' : 'a regular employee'}.`,
      })
      load()
    } catch (e) {
      toast({ title: 'Could not change role', msg: errMessage(e), type: 'error' })
    } finally {
      setBusy(null)
    }
  }

  const admins = users.filter((u) => u.role === 'admin' && u.is_active).length

  return (
    <div className="panel">
      <div className="panel-inner">
        <div className="panel-header">
          <div>
            <h2>Users &amp; Access</h2>
            <p>
              Accounts that can sign in. Grant HR admin access to colleagues who need to manage
              policies, employees and the audit trail.
            </p>
          </div>
        </div>

        <div className="data-grid">
          <div className="grid-row head" style={{ gridTemplateColumns: GRID }}>
            <div>Name</div><div>Company email</div><div>Department</div><div>Role</div>
            <div style={{ textAlign: 'right' }}>Access</div>
          </div>

          {users.length === 0 && <div className="empty-state">No accounts yet.</div>}

          {users.map((u) => {
            const isMe = u.id === me?.id
            const isAdmin = u.role === 'admin'
            // Mirrors the server guardrails so the UI never offers an action
            // the API will refuse.
            const lastAdmin = isAdmin && admins <= 1
            return (
              <div className="grid-row" key={u.id} style={{ gridTemplateColumns: GRID, opacity: u.is_active ? 1 : 0.5 }}>
                <div style={{ fontWeight: 500 }}>
                  {u.full_name}{isMe && <span className="sub"> (you)</span>}
                  {!u.is_active && <span className="sub"> · deactivated</span>}
                </div>
                <div className="policy-meta" style={{ fontFamily: 'var(--mono)', fontSize: 11 }}>{u.email}</div>
                <div className="policy-meta">{u.department ?? '—'}</div>
                <div>
                  <span className={`nav-role-badge ${u.role}`}>
                    {isAdmin ? 'HR Admin' : 'Employee'}
                  </span>
                </div>
                <div className="row-actions">
                  {isAdmin ? (
                    <button
                      className="btn ghost"
                      disabled={busy === u.id || isMe || lastAdmin || !u.is_active}
                      title={isMe ? 'You cannot revoke your own access'
                        : lastAdmin ? 'At least one admin must remain' : 'Revoke admin access'}
                      onClick={() => setRole(u, 'employee')}
                    >
                      <ShieldOff size={14} /> Revoke
                    </button>
                  ) : (
                    <button
                      className="btn primary"
                      disabled={busy === u.id || !u.is_active}
                      title="Grant HR admin access"
                      onClick={() => setRole(u, 'admin')}
                    >
                      <ShieldCheck size={14} /> Make admin
                    </button>
                  )}
                </div>
              </div>
            )
          })}
        </div>

        <p style={{ fontSize: 12, color: 'var(--text-dim)', marginTop: 16 }}>
          <UserRound size={12} style={{ verticalAlign: 'middle', marginRight: 6 }} />
          The first administrator is created on the server with{' '}
          <code>python -m app.provision create-admin</code>. At least one admin must always remain.
        </p>
      </div>
    </div>
  )
}
