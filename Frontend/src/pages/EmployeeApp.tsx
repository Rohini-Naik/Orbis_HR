import { TopNav } from '../components/TopNav'
import { ChatView } from '../features/chat/ChatView'

export function EmployeeApp() {
  return (
    <div className="app-shell">
      <TopNav />
      <ChatView variant="employee" />
    </div>
  )
}
