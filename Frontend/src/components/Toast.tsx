import { createContext, useCallback, useContext, useState, type ReactNode } from 'react'
import { Check, AlertTriangle } from 'lucide-react'

interface ToastData {
  title: string
  msg?: string
  type?: 'success' | 'error'
}

const ToastContext = createContext<(t: ToastData) => void>(() => {})

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toast, setToast] = useState<ToastData | null>(null)

  const show = useCallback((t: ToastData) => {
    setToast(t)
    setTimeout(() => setToast(null), 3500)
  }, [])

  return (
    <ToastContext.Provider value={show}>
      {children}
      {toast && (
        <div className={`toast ${toast.type === 'error' ? 'error' : ''}`}>
          <div className="toast-icon">
            {toast.type === 'error' ? <AlertTriangle size={16} /> : <Check size={16} />}
          </div>
          <div>
            <div className="toast-title">{toast.title}</div>
            {toast.msg && <div className="toast-msg">{toast.msg}</div>}
          </div>
        </div>
      )}
    </ToastContext.Provider>
  )
}

// eslint-disable-next-line react-refresh/only-export-components
export function useToast() {
  return useContext(ToastContext)
}
