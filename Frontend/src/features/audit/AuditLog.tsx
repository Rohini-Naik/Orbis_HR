import { useEffect, useState, type ReactNode } from 'react'
import {
  Activity, CheckCircle2, Database, Download, FileText, MessageSquare, ShieldAlert,
  Trash2, Upload, UserPlus, Zap,
} from 'lucide-react'
import { api, errMessage } from '../../api/client'
import type { AuditEntry, AuditStats } from '../../api/types'
import { useToast } from '../../components/Toast'

function fmtTime(s: string) {
  return new Date(s).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

function describe(e: AuditEntry): string {
  // Blocked entries reveal content so an admin can investigate the flag.
  if (e.hallucination_blocked) return `Blocked — not grounded · "${e.question ?? ''}"`
  // Normal chat activity is shown as metadata only (content redacted for privacy).
  switch (e.action) {
    case 'chat':
      if (e.route === 'sql') return 'NL→SQL data query (read-only)'
      if (e.route === 'rag') return 'Policy answer (RAG)'
      return 'Conversation'
    case 'upload': return `Uploaded ${e.question} · indexed`
    case 'delete': return `Removed ${e.question} from index`
    case 'employee': return e.question ?? 'Employee record change'
    default: return e.question ?? e.action
  }
}

function ActionIcon({ e }: { e: AuditEntry }) {
  if (e.action === 'upload') return <Upload size={14} />
  if (e.action === 'delete') return <Trash2 size={14} />
  if (e.action === 'employee') return <UserPlus size={14} />
  if (e.route === 'sql') return <Database size={14} />
  if (e.route === 'rag') return <FileText size={14} />
  return <MessageSquare size={14} />
}

function actionClass(e: AuditEntry) {
  if (['upload', 'delete', 'employee'].includes(e.action)) return e.action
  return e.route ?? 'rag'
}

export function AuditLog() {
  const toast = useToast()
  const [stats, setStats] = useState<AuditStats | null>(null)
  const [entries, setEntries] = useState<AuditEntry[]>([])

  useEffect(() => {
    api.get<AuditStats>('/audit/stats').then((r) => setStats(r.data)).catch(() => {})
    api.get<AuditEntry[]>('/audit').then((r) => setEntries(r.data)).catch(() => {})
  }, [])

  async function exportCsv() {
    try {
      const res = await api.get('/audit/export', { responseType: 'blob' })
      const url = URL.createObjectURL(res.data as Blob)
      const a = document.createElement('a')
      a.href = url; a.download = 'audit_log.csv'; a.click()
      URL.revokeObjectURL(url)
    } catch (e) {
      toast({ title: 'Export failed', msg: errMessage(e), type: 'error' })
    }
  }

  return (
    <div className="panel">
      <div className="panel-inner">
        <div className="panel-header">
          <div>
            <h2>Audit Log</h2>
            <p>Every AI response, every policy change, every query — traceable for compliance.</p>
          </div>
          <button className="btn-solid" onClick={exportCsv}><Download size={15} /> Export CSV</button>
        </div>

        <div className="stats-bar">
          <Stat icon={<Activity size={11} />} label="Events today" value={stats?.events_today ?? '—'} />
          <Stat icon={<ShieldAlert size={11} />} label="Flagged for review" value={stats?.flagged_for_review ?? '—'} danger />
          <Stat icon={<Zap size={11} />} label="Avg response" value={stats?.avg_response_ms != null ? (stats.avg_response_ms / 1000).toFixed(1) : '—'} unit="s" />
          <Stat icon={<CheckCircle2 size={11} />} label="Verification pass-rate" value={stats ? (stats.verification_pass_rate * 100).toFixed(1) : '—'} unit="%" />
        </div>

        <div className="data-grid">
          {entries.length === 0 && <div className="empty-state">No audit events yet.</div>}
          {entries.map((e) => (
            <div className="grid-row audit-cols" key={e.id}>
              <div className="audit-time">{fmtTime(e.created_at)}</div>
              <div className={`audit-action ${actionClass(e)}`}>
                <div className="ico"><ActionIcon e={e} /></div>
                <div className="audit-desc">{describe(e)}</div>
              </div>
              <div className="audit-user">{e.username ?? '—'} {e.role ? `(${e.role})` : ''}</div>
              <div>
                <span className={`status-pill ${e.status === 'Blocked' ? 'blocked' : e.status === 'Complete' ? 'complete' : ''}`}>
                  <span className="dot" /> {e.status}
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

function Stat({ icon, label, value, unit, danger }: { icon: ReactNode; label: string; value: ReactNode; unit?: string; danger?: boolean }) {
  return (
    <div className="stat-card">
      <div className="stat-label">{icon} {label}</div>
      <div className="stat-value" style={danger ? { color: 'var(--danger)' } : undefined}>{value}{unit && <span className="unit">{unit}</span>}</div>
    </div>
  )
}
