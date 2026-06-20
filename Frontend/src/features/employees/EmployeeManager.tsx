import { useEffect, useState } from 'react'
import { Search, Trash2, UserPlus } from 'lucide-react'
import { api, errMessage } from '../../api/client'
import type { Employee, EmployeeListResponse } from '../../api/types'
import { useToast } from '../../components/Toast'

type FieldType = 'text' | 'number' | 'date' | 'select'
interface Field { key: string; label: string; type: FieldType; required?: boolean; options?: string[] }

const FIELDS: Field[] = [
  { key: 'EmployeeID', label: 'Employee ID', type: 'number', required: true },
  { key: 'EmployeeName', label: 'Full name', type: 'text', required: true },
  { key: 'Age', label: 'Age', type: 'number' },
  { key: 'Gender', label: 'Gender', type: 'select', options: ['Male', 'Female', 'Other'] },
  { key: 'Location', label: 'Location', type: 'text' },
  { key: 'Department', label: 'Department', type: 'text' },
  { key: 'Role', label: 'Role', type: 'text' },
  { key: 'YearsAtCompany', label: 'Years at company', type: 'number' },
  { key: 'DateOfJoining', label: 'Date of joining', type: 'date' },
  { key: 'YearsInCurrentRole', label: 'Years in current role', type: 'number' },
  { key: 'EducationLevel', label: 'Education', type: 'select', options: ['Diploma', 'Bachelor', 'Master', 'PhD'] },
  { key: 'MonthlySalaryINR', label: 'Monthly salary (INR)', type: 'number' },
  { key: 'WorkHoursPerWeek', label: 'Work hours / week', type: 'number' },
  { key: 'ProjectsHandled', label: 'Projects handled', type: 'number' },
  { key: 'TrainingHoursLastYear', label: 'Training hours (last yr)', type: 'number' },
  { key: 'SickLeavesLastYear', label: 'Sick leaves (last yr)', type: 'number' },
  { key: 'OvertimeHoursLastMonth', label: 'Overtime hrs (last mo)', type: 'number' },
  { key: 'ManagerRating', label: 'Manager rating', type: 'number' },
  { key: 'DisciplinaryNotices', label: 'Disciplinary notices', type: 'number' },
  { key: 'PolicyViolationsLastYear', label: 'Policy violations (last yr)', type: 'number' },
  { key: 'PerformanceRating', label: 'Performance rating', type: 'number' },
  { key: 'PromotionLast2Years', label: 'Promoted in 2 yrs', type: 'select', options: ['Yes', 'No'] },
  { key: 'ComplianceRiskLevel', label: 'Compliance risk', type: 'select', options: ['Low', 'Medium', 'High'] },
  { key: 'AttritionRisk', label: 'Attrition risk', type: 'select', options: ['Low', 'Medium', 'High'] },
]
const NUMERIC = new Set(FIELDS.filter((f) => f.type === 'number').map((f) => f.key))

export function EmployeeManager() {
  const toast = useToast()
  const [form, setForm] = useState<Record<string, string>>({})
  const [saving, setSaving] = useState(false)
  const [employees, setEmployees] = useState<Employee[]>([])
  const [total, setTotal] = useState(0)
  const [search, setSearch] = useState('')
  const [error, setError] = useState('')

  useEffect(() => { load() }, [search])

  function load() {
    api.get<EmployeeListResponse>('/employees', { params: search ? { search } : {} })
      .then((r) => { setEmployees(r.data.employees); setTotal(r.data.total) })
      .catch((e) => setError(errMessage(e)))
  }

  function set(key: string, value: string) { setForm((f) => ({ ...f, [key]: value })) }

  async function submit() {
    setError('')
    if (!form.EmployeeID || !form.EmployeeName) {
      setError('Employee ID and full name are required.')
      return
    }
    const payload: Record<string, unknown> = {}
    for (const [k, v] of Object.entries(form)) {
      if (v === '') continue
      payload[k] = NUMERIC.has(k) ? Number(v) : v
    }
    setSaving(true)
    try {
      await api.post('/employees', payload)
      toast({ title: 'Employee added', msg: `${form.EmployeeName} (ID ${form.EmployeeID}) was created.` })
      setForm({})
      load()
    } catch (e) {
      setError(errMessage(e))
    } finally {
      setSaving(false)
    }
  }

  async function remove(id: number) {
    try {
      await api.delete(`/employees/${id}`)
      toast({ title: 'Employee removed', msg: `Employee ${id} deleted.` })
      load()
    } catch (e) {
      toast({ title: 'Delete failed', msg: errMessage(e), type: 'error' })
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
            <input placeholder="Search employees by name, department, role…" value={search} onChange={(e) => setSearch(e.target.value)} />
          </div>
          <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>{total.toLocaleString()} total</div>
        </div>

        <div className="data-grid">
          <div className="grid-row head" style={{ gridTemplateColumns: '90px 1fr 140px 140px 130px 80px' }}>
            <div>ID</div><div>Name</div><div>Department</div><div>Role</div><div>Salary (INR)</div>
            <div style={{ textAlign: 'right' }}>Actions</div>
          </div>
          {employees.length === 0 && <div className="empty-state">No employees found.</div>}
          {employees.map((e) => (
            <div className="grid-row" key={e.EmployeeID} style={{ gridTemplateColumns: '90px 1fr 140px 140px 130px 80px' }}>
              <div className="policy-meta">{e.EmployeeID}</div>
              <div style={{ fontWeight: 500 }}>{e.EmployeeName}</div>
              <div className="policy-meta">{String(e.Department ?? '—')}</div>
              <div className="policy-meta">{String(e.Role ?? '—')}</div>
              <div className="policy-meta">{e.MonthlySalaryINR ? Number(e.MonthlySalaryINR).toLocaleString() : '—'}</div>
              <div className="row-actions">
                <button className="action-btn delete" title="Delete" onClick={() => remove(e.EmployeeID)}><Trash2 size={15} /></button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
