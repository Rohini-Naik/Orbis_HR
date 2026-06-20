export type Role = 'admin' | 'employee'

export interface TokenResponse {
  access_token: string
  token_type: string
  email: string
  full_name: string
  role: Role
}

export interface UserProfile {
  id: number
  email: string
  full_name: string
  role: Role
  employee_id: number | null
  department: string | null
}

export interface Source {
  idx: number
  source: string | null
  page: number | null
  section: string | null
  score: number | null
}

export interface ChatResponse {
  conversation_id: number
  route: 'rag' | 'sql' | 'chat'
  answer: string
  sources: Source[]
  sql: string | null
  rows: Record<string, unknown>[] | null
  confidence: number | null
  hallucination_blocked: boolean
}

export interface ConversationSummary {
  id: number
  title: string
  created_at: string
}

export interface Message {
  role: 'user' | 'assistant'
  content: string
  created_at: string
}

export interface ConversationDetail extends ConversationSummary {
  messages: Message[]
}

export interface PolicyFile {
  id: number
  filename: string
  category: string | null
  chunks: number
  size_bytes: number
  status: string
  uploaded_by: string | null
  uploaded_at: string
}

export interface PolicyStats {
  total_policies: number
  indexed_chunks: number
  queries_served: number
  accuracy_rate: number
}

export interface AuditEntry {
  id: number
  username: string | null
  role: string | null
  action: string
  question: string | null
  route: string | null
  sql: string | null
  confidence: number | null
  latency_ms: number | null
  hallucination_blocked: boolean
  status: string
  created_at: string
}

export interface AuditStats {
  events_today: number
  flagged_for_review: number
  avg_response_ms: number | null
  verification_pass_rate: number
}

export interface Employee {
  EmployeeID: number
  EmployeeName: string
  [key: string]: unknown
}

export interface EmployeeListResponse {
  total: number
  employees: Employee[]
}
