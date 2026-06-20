import { useState } from 'react'
import { FolderOpen, MessageSquare, ScrollText, UserPlus } from 'lucide-react'
import { TopNav } from '../components/TopNav'
import { ChatView } from '../features/chat/ChatView'
import { PolicyLibrary } from '../features/policies/PolicyLibrary'
import { AuditLog } from '../features/audit/AuditLog'
import { EmployeeManager } from '../features/employees/EmployeeManager'

type Tab = 'chat' | 'policies' | 'audit' | 'employees'

export function AdminApp() {
  const [tab, setTab] = useState<Tab>('chat')

  return (
    <div className="app-shell">
      <TopNav />
      <div className="tab-nav">
        <button className={`tab-btn ${tab === 'chat' ? 'active' : ''}`} onClick={() => setTab('chat')}>
          <MessageSquare size={15} /> AI Co-pilot
        </button>
        <button className={`tab-btn ${tab === 'policies' ? 'active' : ''}`} onClick={() => setTab('policies')}>
          <FolderOpen size={15} /> Policy Library
        </button>
        <button className={`tab-btn ${tab === 'audit' ? 'active' : ''}`} onClick={() => setTab('audit')}>
          <ScrollText size={15} /> Audit Log
        </button>
        <button className={`tab-btn ${tab === 'employees' ? 'active' : ''}`} onClick={() => setTab('employees')}>
          <UserPlus size={15} /> Employees
        </button>
      </div>

      {tab === 'chat' && <ChatView variant="admin" />}
      {tab === 'policies' && <PolicyLibrary />}
      {tab === 'audit' && <AuditLog />}
      {tab === 'employees' && <EmployeeManager />}
    </div>
  )
}
