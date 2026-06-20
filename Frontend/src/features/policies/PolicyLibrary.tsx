import { useEffect, useRef, useState, type ReactNode } from 'react'
import {
  CloudUpload, Database, Download, Eye, FileStack, FileText,
  MessageCircleQuestion, Search, ShieldCheck, Trash2, Upload, X,
} from 'lucide-react'
import { api, errMessage } from '../../api/client'
import type { PolicyFile, PolicyStats } from '../../api/types'
import { useToast } from '../../components/Toast'

const CATEGORIES = ['all', 'Leave', 'Conduct', 'Benefits', 'Privacy', 'Work']

function fmtBytes(n: number) {
  if (!n) return '—'
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(0)} KB`
  return `${(n / 1024 / 1024).toFixed(1)} MB`
}
function fmtDate(s: string) {
  return new Date(s).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })
}
const catClass = (c?: string | null) => (c ?? 'general').toLowerCase()

export function PolicyLibrary() {
  const toast = useToast()
  const [stats, setStats] = useState<PolicyStats | null>(null)
  const [files, setFiles] = useState<PolicyFile[]>([])
  const [search, setSearch] = useState('')
  const [category, setCategory] = useState('all')
  const [viewing, setViewing] = useState<{ title: string; content: string } | null>(null)
  const [toDelete, setToDelete] = useState<PolicyFile | null>(null)
  const [uploading, setUploading] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)

  useEffect(() => { load() }, [search, category])

  function loadStats() { api.get<PolicyStats>('/policies/stats').then((r) => setStats(r.data)).catch(() => {}) }
  function load() {
    loadStats()
    const params: Record<string, string> = {}
    if (search) params.search = search
    if (category !== 'all') params.category = category
    api.get<PolicyFile[]>('/policies', { params }).then((r) => setFiles(r.data)).catch(() => {})
  }

  async function upload(file: File) {
    setUploading(true)
    toast({ title: 'Indexing started', msg: `"${file.name}" is being chunked & embedded…` })
    try {
      const fd = new FormData()
      fd.append('file', file)
      await api.post('/policies', fd)
      toast({ title: 'Indexed', msg: `"${file.name}" is now searchable.` })
      load()
    } catch (e) {
      toast({ title: 'Upload failed', msg: errMessage(e), type: 'error' })
    } finally {
      setUploading(false)
    }
  }

  async function view(p: PolicyFile) {
    try {
      const { data } = await api.get<{ content: string }>(`/policies/${p.id}`)
      setViewing({ title: p.filename, content: (data.content || '').slice(0, 20000) || 'No extractable text.' })
    } catch (e) {
      toast({ title: 'Could not open', msg: errMessage(e), type: 'error' })
    }
  }

  async function download(p: PolicyFile) {
    try {
      const res = await api.get(`/policies/${p.id}/download`, { responseType: 'blob' })
      const url = URL.createObjectURL(res.data as Blob)
      const a = document.createElement('a')
      a.href = url; a.download = p.filename; a.click()
      URL.revokeObjectURL(url)
    } catch (e) {
      toast({ title: 'Download failed', msg: errMessage(e), type: 'error' })
    }
  }

  async function confirmDelete() {
    if (!toDelete) return
    try {
      await api.delete(`/policies/${toDelete.id}`)
      toast({ title: 'Policy removed', msg: `"${toDelete.filename}" was un-indexed.` })
      setToDelete(null)
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
            <h2>Policy Library</h2>
            <p>Documents the RAG engine uses to answer questions. Upload, view, or remove policies.</p>
          </div>
          <button className="btn-solid" disabled={uploading} onClick={() => fileRef.current?.click()}>
            <Upload size={15} /> Upload Policy
          </button>
          <input ref={fileRef} type="file" hidden accept=".pdf,.docx,.txt"
            onChange={(e) => e.target.files?.[0] && upload(e.target.files[0])} />
        </div>

        <div className="stats-bar">
          <StatCard icon={<FileStack size={11} />} label="Total policies" value={stats?.total_policies ?? '—'} />
          <StatCard icon={<Database size={11} />} label="Indexed chunks" value={stats ? stats.indexed_chunks.toLocaleString() : '—'} />
          <StatCard icon={<MessageCircleQuestion size={11} />} label="Queries served" value={stats?.queries_served ?? '—'} />
          <StatCard icon={<ShieldCheck size={11} />} label="Verified accuracy"
            value={stats ? `${(stats.accuracy_rate * 100).toFixed(1)}` : '—'} unit="%" />
        </div>

        <div className="upload-zone" onClick={() => fileRef.current?.click()}
          onDragOver={(e) => { e.preventDefault() }}
          onDrop={(e) => { e.preventDefault(); e.dataTransfer.files?.[0] && upload(e.dataTransfer.files[0]) }}>
          <div className="upload-icon"><CloudUpload size={24} /></div>
          <div className="upload-title">Drop a policy document here</div>
          <div className="upload-sub">PDF, DOCX, or TXT · Auto-indexed on upload</div>
        </div>

        <div className="toolbar">
          <div className="search-input">
            <Search size={15} />
            <input placeholder="Search policies by name…" value={search} onChange={(e) => setSearch(e.target.value)} />
          </div>
          <div className="filter-chips">
            {CATEGORIES.map((c) => (
              <button key={c} className={`chip ${category === c ? 'active' : ''}`} onClick={() => setCategory(c)}>
                {c === 'all' ? 'All' : c}
              </button>
            ))}
          </div>
        </div>

        <div className="data-grid">
          <div className="grid-row head policy-cols">
            <div /><div>Policy Document</div><div>Category</div><div>Uploaded</div><div>Status</div>
            <div style={{ textAlign: 'right' }}>Actions</div>
          </div>
          {files.length === 0 && <div className="empty-state">No policies match your filter.</div>}
          {files.map((p) => {
            const isPdf = p.filename.toLowerCase().endsWith('.pdf')
            return (
              <div className="grid-row policy-cols" key={p.id}>
                <div className={`file-icon ${isPdf ? 'pdf' : 'doc'}`}><FileText size={16} /></div>
                <div className="policy-name">
                  {p.filename}
                  <span className="sub">{p.chunks} chunks · {fmtBytes(p.size_bytes)}</span>
                </div>
                <div><span className={`category-badge ${catClass(p.category)}`}>{p.category ?? 'General'}</span></div>
                <div className="policy-meta">{fmtDate(p.uploaded_at)}</div>
                <div><span className="status-pill"><span className="dot" /> Indexed</span></div>
                <div className="row-actions">
                  <button className="action-btn" title="View" onClick={() => view(p)}><Eye size={15} /></button>
                  <button className="action-btn" title="Download" onClick={() => download(p)}><Download size={15} /></button>
                  <button className="action-btn delete" title="Delete" onClick={() => setToDelete(p)}><Trash2 size={15} /></button>
                </div>
              </div>
            )
          })}
        </div>
      </div>

      {viewing && (
        <div className="modal-backdrop" onClick={(e) => e.target === e.currentTarget && setViewing(null)}>
          <div className="modal">
            <div className="modal-header">
              <div className="file-icon pdf"><FileText size={16} /></div>
              <div className="modal-title">{viewing.title}</div>
              <button className="modal-close" onClick={() => setViewing(null)}><X size={16} /></button>
            </div>
            <div className="modal-body"><p>{viewing.content}</p></div>
          </div>
        </div>
      )}

      {toDelete && (
        <div className="modal-backdrop" onClick={(e) => e.target === e.currentTarget && setToDelete(null)}>
          <div className="modal sm">
            <div className="modal-header">
              <div className="file-icon" style={{ background: 'var(--danger-dim)', color: 'var(--danger)', border: '1px solid rgba(255,123,123,.3)' }}>
                <Trash2 size={16} />
              </div>
              <div className="modal-title">Delete this policy?</div>
              <button className="modal-close" onClick={() => setToDelete(null)}><X size={16} /></button>
            </div>
            <div className="modal-body">
              <p style={{ margin: 0 }}>Removing <strong style={{ color: 'var(--text)' }}>{toDelete.filename}</strong> will un-index it from the RAG engine. This action is logged in the audit trail.</p>
            </div>
            <div className="modal-footer">
              <button className="btn ghost" onClick={() => setToDelete(null)}>Cancel</button>
              <button className="btn danger" onClick={confirmDelete}><Trash2 size={14} /> Delete & un-index</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function StatCard({ icon, label, value, unit }: { icon: ReactNode; label: string; value: ReactNode; unit?: string }) {
  return (
    <div className="stat-card">
      <div className="stat-label">{icon} {label}</div>
      <div className="stat-value">{value}{unit && <span className="unit">{unit}</span>}</div>
    </div>
  )
}
