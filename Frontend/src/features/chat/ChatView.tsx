import { useEffect, useRef, useState } from 'react'
import {
  ArrowUp, Brain, CheckCircle2, Database, FileText, GitFork, Lock,
  MessageCircle, MessageSquare, Plus, ShieldCheck, Sparkles,
} from 'lucide-react'
import { api, errMessage } from '../../api/client'
import type { ChatResponse, ConversationDetail, ConversationSummary } from '../../api/types'
import { useToast } from '../../components/Toast'

interface DisplayMsg {
  role: 'user' | 'assistant'
  content: string
  meta?: ChatResponse
}

export function ChatView({ variant }: { variant: 'employee' | 'admin' }) {
  const toast = useToast()
  const [conversations, setConversations] = useState<ConversationSummary[]>([])
  const [activeId, setActiveId] = useState<number | null>(null)
  const [messages, setMessages] = useState<DisplayMsg[]>([])
  const [suggestions, setSuggestions] = useState<string[]>([])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const scrollRef = useRef<HTMLDivElement>(null)

  const isAdmin = variant === 'admin'

  useEffect(() => {
    api.get<string[]>('/chat/suggested-questions').then((r) => setSuggestions(r.data)).catch(() => {})
    refreshConversations()
  }, [])

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight })
  }, [messages, sending])

  function refreshConversations() {
    api.get<ConversationSummary[]>('/chat/conversations').then((r) => setConversations(r.data)).catch(() => {})
  }

  function newChat() {
    setActiveId(null)
    setMessages([])
    setInput('')
  }

  async function openConversation(id: number) {
    try {
      const { data } = await api.get<ConversationDetail>(`/chat/conversations/${id}`)
      setActiveId(id)
      setMessages(data.messages.map((m) => ({ role: m.role, content: m.content })))
    } catch (e) {
      toast({ title: 'Could not open conversation', msg: errMessage(e), type: 'error' })
    }
  }

  async function send(text: string) {
    const question = text.trim()
    if (!question || sending) return
    setInput('')
    setMessages((m) => [...m, { role: 'user', content: question }])
    setSending(true)
    try {
      const { data } = await api.post<ChatResponse>('/chat', { question, conversation_id: activeId })
      setActiveId(data.conversation_id)
      setMessages((m) => [...m, { role: 'assistant', content: data.answer, meta: data }])
      refreshConversations()
    } catch (e) {
      setMessages((m) => [...m, { role: 'assistant', content: `⚠️ ${errMessage(e)}` }])
    } finally {
      setSending(false)
    }
  }

  return (
    <div className="app-body">
      {/* Sidebar */}
      <div className="sidebar">
        <div className="sidebar-header">
          <button className="new-chat-btn" onClick={newChat}>
            <Plus size={16} /> New conversation
          </button>
        </div>
        <div className="sidebar-section scroll">
          <div className="sidebar-label"><MessageSquare size={11} /> Recent</div>
          <div className="conv-list">
            {conversations.length === 0 && <div style={{ fontSize: 12, color: 'var(--text-dim)' }}>No conversations yet</div>}
            {conversations.map((c) => (
              <div key={c.id} className={`conv-item ${activeId === c.id ? 'active' : ''}`} onClick={() => openConversation(c.id)}>
                <MessageCircle size={14} /> {c.title}
              </div>
            ))}
          </div>
        </div>
        <div className="sidebar-section">
          <div className="sidebar-label"><GitFork size={11} /> How Orbis works</div>
          <div className="workflow">
            <div className="workflow-title">Your query flows through:</div>
            <div className="workflow-step"><div className="step-icon"><MessageSquare size={12} /></div><span>Your question</span></div>
            <div className="workflow-arrow">↓</div>
            <div className="workflow-step"><div className="step-icon"><GitFork size={12} /></div><span>Router LLM</span></div>
            <div className="workflow-arrow">↓</div>
            <div className="workflow-step rag"><div className="step-icon"><FileText size={12} /></div><span>Policy RAG</span></div>
            <div className="workflow-step sql"><div className="step-icon"><Database size={12} /></div><span>NL → SQL</span></div>
            <div className="workflow-arrow">↓</div>
            <div className="workflow-step memory"><div className="step-icon"><Brain size={12} /></div><span>Memory + verify</span></div>
          </div>
        </div>
      </div>

      {/* Main */}
      <div className="main-area">
        <div className="chat-header">
          <div>
            <div className="chat-title">{isAdmin ? 'Admin Co-pilot' : 'Compliance Co-pilot'}</div>
            <div className="chat-meta">
              <ShieldCheck size={11} color={isAdmin ? 'var(--accent-warm)' : 'var(--accent)'} />
              {isAdmin ? 'Elevated access · Org-wide data queries' : 'On-premise · Memory active · Hallucination filter on'}
            </div>
          </div>
        </div>

        <div className="messages-area" ref={scrollRef}>
          <div className="messages-inner">
            {messages.length === 0 && (
              <Welcome isAdmin={isAdmin} suggestions={suggestions} onPick={send} />
            )}
            {messages.map((m, i) => <MessageBubble key={i} msg={m} />)}
            {sending && (
              <div className="message ai">
                <div className="msg-avatar"><Sparkles size={14} /></div>
                <div className="msg-body">
                  <div className="msg-header"><span className="msg-author">Orbis</span><span className="msg-time">thinking…</span></div>
                  <div className="typing-indicator"><span /><span /><span /></div>
                </div>
              </div>
            )}
          </div>
        </div>

        <div className="input-area">
          <div className="input-wrap">
            <div className="input-box">
              <textarea
                className="input-field"
                placeholder={isAdmin ? 'Ask about company-wide policy or aggregate HR data…' : 'Ask about a policy or your data…'}
                value={input}
                rows={1}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(input) } }}
              />
              <div className="input-controls">
                <div className="input-hints">
                  <span className="hint-pill"><Brain size={10} /> Memory on</span>
                  <span className="hint-pill"><Lock size={10} /> {isAdmin ? 'Auto-audit' : 'Local only'}</span>
                </div>
                <button className="send-btn" onClick={() => send(input)} disabled={!input.trim() || sending}>
                  <ArrowUp size={16} />
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

function Welcome({ isAdmin, suggestions, onPick }: { isAdmin: boolean; suggestions: string[]; onPick: (q: string) => void }) {
  return (
    <div className="welcome-block">
      <div className={`welcome-icon ${isAdmin ? 'admin' : ''}`}><Sparkles size={28} /></div>
      <h1 className="welcome-title">
        {isAdmin ? <>Ask <em>org-level</em> questions with a full audit trail.</> : <>Ask anything about <em>HR policy</em> or your <em>data</em>.</>}
      </h1>
      <p className="welcome-sub">
        I route your question to the right engine, cite my source, and verify the answer before showing it.
      </p>
      <div className="suggestions">
        {suggestions.map((s, i) => (
          <button key={i} className="suggestion-card" onClick={() => onPick(s)}>
            <div className="suggestion-text">{s}</div>
          </button>
        ))}
      </div>
    </div>
  )
}

function MessageBubble({ msg }: { msg: DisplayMsg }) {
  if (msg.role === 'user') {
    return (
      <div className="message user">
        <div className="msg-avatar">You</div>
        <div className="msg-body">
          <div className="msg-header"><span className="msg-author">You</span></div>
          <div className="msg-content">{msg.content}</div>
        </div>
      </div>
    )
  }
  const meta = msg.meta
  return (
    <div className="message ai">
      <div className="msg-avatar"><Sparkles size={14} /></div>
      <div className="msg-body">
        <div className="msg-header">
          <span className="msg-author">Orbis</span>
          {meta && meta.route !== 'chat' && (
            <span className={`route-badge ${meta.route}`}>
              {meta.route === 'sql' ? <Database size={11} /> : <FileText size={11} />}
              {meta.route === 'sql' ? 'Data · NL→SQL' : 'Policy · RAG'}
            </span>
          )}
        </div>
        <div className="msg-content">{msg.content}</div>
        {meta && meta.route !== 'chat' && <Extras meta={meta} />}
      </div>
    </div>
  )
}

function Extras({ meta }: { meta: ChatResponse }) {
  return (
    <div className="msg-extras">
      {meta.sources?.map((s) => (
        <div className="source-citation" key={s.idx}>
          <div className="src-icon"><FileText size={14} /></div>
          <div className="src-info">
            <div className="src-title">[{s.idx}] {s.source}</div>
            <div className="src-detail">
              {s.section ?? 'Section'} · p{s.page}
              {s.score != null && ` · relevance ${Math.round(s.score * 100)}%`}
            </div>
          </div>
        </div>
      ))}
      {meta.sql && (
        <div className="sql-block">
          <div className="sql-label">Generated SQL (read-only)</div>
          <div>{meta.sql}</div>
          {meta.rows && meta.rows.length > 0 && <RowsTable rows={meta.rows} />}
        </div>
      )}
      <div className="verification-bar">
        {meta.hallucination_blocked ? (
          <span className="check-pill blocked"><ShieldCheck size={12} /> Blocked — not grounded</span>
        ) : (
          <span className="check-pill"><ShieldCheck size={12} /> {meta.route === 'sql' ? 'Verified against DB' : 'Grounded in source'}</span>
        )}
        <span className="sep" />
        {meta.confidence != null && <span><CheckCircle2 size={11} /> Confidence {Math.round(meta.confidence * 100)}%</span>}
        {meta.route === 'sql' && <span><Lock size={11} /> Read-only access</span>}
        <span className="sep" />
        <span><Brain size={11} /> Memory updated</span>
      </div>
    </div>
  )
}

function RowsTable({ rows }: { rows: Record<string, unknown>[] }) {
  const cols = Object.keys(rows[0])
  return (
    <table className="rows-table">
      <thead><tr>{cols.map((c) => <th key={c}>{c}</th>)}</tr></thead>
      <tbody>
        {rows.slice(0, 10).map((r, i) => (
          <tr key={i}>{cols.map((c) => <td key={c}>{String(r[c])}</td>)}</tr>
        ))}
      </tbody>
    </table>
  )
}
