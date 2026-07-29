import { useEffect, useState } from 'react'
import { RotateCcw, Search, UserMinus, UserPlus } from 'lucide-react'
import { api, errMessage } from '../../api/client'
import type { Employee, EmployeeListResponse } from '../../api/types'
import { useToast } from '../../components/Toast'

type FieldType = 'text' | 'number' | 'date' | 'select'
interface Field { key: string; label: string; type: FieldType; required?: boolean; options?: string[] }

const DEPARTMENTS = ['Engineering', 'HR', 'Finance', 'Legal', 'Marketing', 'Sales',
  'Operations', 'Customer Support']
const RATINGS = ['Exceeds Expectations', 'Meets Expectations', 'Needs Improvement']

const FIELDS: Field[] = [
  { key: 'FullName', label: 'Full name', type: 'text', required: true },
  { key: 'PersonalEmail', label: 'Personal email (invitation is sent here)', type: 'text', required: true },
  { key: 'Role', label: 'Role / designation', type: 'text' },
  { key: 'Department', label: 'Department', type: 'select', options: DEPARTMENTS },
  { key: 'Location', label: 'Location', type: 'text' },
  { key: 'DateOfJoining', label: 'Date of joining', type: 'date' },
  { key: 'ManagerID', label: 'Manager ID (e.g. EMP1003)', type: 'text' },
  { key: 'ManagerName', label: 'Manager name', type: 'text' },
  { key: 'EmploymentType', label: 'Employment type', type: 'select', options: ['Full-Time', 'Contract'] },
  { key: 'AnnualCTC_INR', label: 'Annual CTC (INR)', type: 'number' },
  { key: 'CasualLeaveBalance', label: 'Casual leave balance', type: 'number' },
  { key: 'CasualLeaveUsed', label: 'Casual leave used', type: 'number' },
  { key: 'SickLeaveBalance', label: 'Sick leave balance', type: 'number' },
  { key: 'SickLeaveUsed', label: 'Sick leave used', type: 'number' },
  { key: 'EarnedLeaveBalance', label: 'Earned leave balance', type: 'number' },
  { key: 'EarnedLeaveUsed', label: 'Earned leave used', type: 'number' },
  { key: 'LastAppraisalDate', label: 'Last appraisal date', type: 'date' },
  { key: 'NextAppraisalDate', label: 'Next appraisal date', type: 'date' },
  { key: 'PerformanceRating', label: 'Performance rating', type: 'select', options: RATINGS },
  { key: 'POSHTrainingCompleted', label: 'POSH training completed', type: 'select', options: ['Yes', 'No'] },
  { key: 'POSHTrainingDate', label: 'POSH training date', type: 'date' },
]
const NUMERIC = new Set(FIELDS.filter((f) => f.type === 'number').map((f) => f.key))
const GRID = '80px 1fr 210px 130px 130px 110px 70px'

export function EmployeeManager() {
  const toast = useToast()
  const [form, setForm] = useState<Record<string, string>>({})
  const [saving, setSaving] = useState(false)
  const [employees, setEmployees] = useState<Employee[]>([])
  const [total, setTotal] = useState(0)
  const [search, setSearch] = useState('')
  const [showExited, setShowExited] = useState(false)
  const [error, setError] = useState('')

  // Debounced so typing in the search box doesn't fire a request per keystroke.
  useEffect(() => {
    const t = setTimeout(load, 250)
    return () => clearTimeout(t)
  }, [search, showExited])

  function load() {
    const params: Record<string, string | boolean> = { include_exited: showExited }
    if (search) params.search = search
    api.get<EmployeeListResponse>('/employees', { params })
      .then((r) => { setEmployees(r.data.employees); setTotal(r.data.total) })
      .catch((e) => setError(errMessage(e)))
  }

  function set(key: string, value: string) { setForm((f) => ({ ...f, [key]: value })) }

  async function submit() {
    setError('')
    if (!form.FullName || !form.PersonalEmail) {
      setError('Full name and personal email are required.')
      return
    }
    const payload: Record<string, unknown> = {}
    for (const [k, v] of Object.entries(form)) {
      if (v === '') continue
      payload[k] = NUMERIC.has(k) ? Number(v) : v
    }
    setSaving(true)
    try {
      const { data } = await api.post<Employee>('/employees', payload)
      toast({
        title: `Employee added — ${data.EmployeeID}`,
        msg: `${data.FullName} · ${String(data.Email)} — invitation sent to ${form.PersonalEmail}.`,
      })
      setForm({})
      load()
    } catch (e) {
      setError(errMessage(e))
    } finally {
      setSaving(false)
    }
  }

  async function deactivate(id: string, name: string) {
    if (!confirm(`Mark ${name} as exited? Their account is disabled and they are signed out. The record is kept.`)) return
    try {
      await api.delete(`/employees/${id}`)
      toast({ title: 'Employee exited', msg: `${name}'s access has been revoked.` })
      load()
    } catch (e) {
      toast({ title: 'Failed', msg: errMessage(e), type: 'error' })
    }
  }

  async function reinstate(id: string, name: string) {
    try {
      await api.post(`/employees/${id}/reinstate`)
      toast({ title: 'Employee reinstated', msg: `${name} is active again.` })
      load()
    } catch (e) {
      toast({ title: 'Failed', msg: errMessage(e), type: 'error' })
    }
  }

  return (
    <div className="panel">
      <div className="panel-inner">
        <div className="panel-header">
          <div>
            <h2>Employees</h2>
            <p>Add new employee records to the HR database. All AI data answers draw from here.</p>
          </div>
        </div>

        <div className="form-card" style={{ marginBottom: 24 }}>
          <h4 style={{ marginTop: 0, marginBottom: 16, fontFamily: 'var(--serif)', fontSize: 18, fontWeight: 400 }}>
            Add new employee
          </h4>
          <div className="form-grid">
            {FIELDS.map((f) => (
              <div className="field-group" key={f.key} style={{ marginBottom: 0 }}>
                <label className="field-label">{f.label}{f.required && ' *'}</label>
                {f.type === 'select' ? (
                  <select className="field-input" value={form[f.key] ?? ''} onChange={(e) => set(f.key, e.target.value)}>
                    <option value="">—</option>
                    {f.options!.map((o) => <option key={o} value={o}>{o}</option>)}
                  </select>
                ) : (
                  <input className="field-input" type={f.type === 'number' ? 'number' : f.type}
                    value={form[f.key] ?? ''} onChange={(e) => set(f.key, e.target.value)} />
                )}
              </div>
            ))}
          </div>
          {error && <div className="login-error" style={{ marginTop: 16 }}>{error}</div>}
          <div className="form-actions">
            <button className="btn ghost" onClick={() => { setForm({}); setError('') }}>Clear</button>
            <button className="btn primary" onClick={submit} disabled={saving}>
              {saving ? <span className="spinner" /> : <><UserPlus size={14} /> Add employee</>}
            </button>
          </div>
        </div>

        <div className="toolbar">
          <div className="search-input">
            <Search size={15} />
            <input placeholder="Search by name, email, department, role…" value={search} onChange={(e) => setSearch(e.target.value)} />
          </div>
          <label style={{ fontSize: 12, color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: 6 }}>
            <input type="checkbox" checked={showExited} onChange={(e) => setShowExited(e.target.checked)} />
            Include exited
          </label>
          <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>{total.toLocaleString()} total</div>
        </div>

        <div className="data-grid">
          <div className="grid-row head" style={{ gridTemplateColumns: GRID }}>
            <div>ID</div><div>Name</div><div>Company email</div><div>Department</div><div>Role</div><div>Status</div>
            <div style={{ textAlign: 'right' }}>Actions</div>
          </div>
          {employees.length === 0 && <div className="empty-state">No employees found.</div>}
          {employees.map((e) => {
            const exited = String(e.Status ?? 'active') === 'exited'
            return (
              <div className="grid-row" key={e.EmployeeID} style={{ gridTemplateColumns: GRID, opacity: exited ? 0.55 : 1 }}>
                <div className="policy-meta">{e.EmployeeID}</div>
                <div style={{ fontWeight: 500 }}>{e.FullName}</div>
                <div className="policy-meta" style={{ fontFamily: 'var(--mono)', fontSize: 11 }}>{String(e.Email ?? '—')}</div>
                <div className="policy-meta">{String(e.Department ?? '—')}</div>
                <div className="policy-meta">{String(e.Role ?? '—')}</div>
                <div>
                  <span className={`status-pill ${exited ? 'blocked' : ''}`}>
                    <span className="dot" /> {exited ? 'Exited' : 'Active'}
                  </span>
                </div>
                <div className="row-actions">
                  {exited ? (
                    <button className="action-btn" title="Reinstate"
                      onClick={() => reinstate(e.EmployeeID, e.FullName)}><RotateCcw size={15} /></button>
                  ) : (
                    <button className="action-btn delete" title="Mark as exited"
                      onClick={() => deactivate(e.EmployeeID, e.FullName)}><UserMinus size={15} /></button>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
