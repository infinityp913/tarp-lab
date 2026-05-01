import { useEffect, useState } from 'react'

export interface ToastMessage {
  id: number
  text: string
  type: 'error' | 'success' | 'info'
}

let _addToast: ((msg: Omit<ToastMessage, 'id'>) => void) | null = null

export function toast(text: string, type: ToastMessage['type'] = 'info') {
  _addToast?.({ text, type })
}

export function ToastContainer() {
  const [toasts, setToasts] = useState<ToastMessage[]>([])
  const [counter, setCounter] = useState(0)

  useEffect(() => {
    _addToast = (msg) => {
      const id = counter + 1
      setCounter(id)
      setToasts((prev) => [...prev, { ...msg, id }])
      setTimeout(() => setToasts((prev) => prev.filter((t) => t.id !== id)), 4000)
    }
    return () => { _addToast = null }
  })

  if (!toasts.length) return null

  return (
    <div style={{
      position: 'fixed', bottom: 24, right: 24, zIndex: 9999,
      display: 'flex', flexDirection: 'column', gap: 8,
    }}>
      {toasts.map((t) => (
        <div key={t.id} style={{
          padding: '10px 16px',
          borderRadius: 8,
          maxWidth: 360,
          fontSize: 14,
          fontWeight: 500,
          boxShadow: '0 4px 16px rgba(0,0,0,0.18)',
          background: t.type === 'error' ? '#ef4444' : t.type === 'success' ? '#22c55e' : '#3b82f6',
          color: '#fff',
          animation: 'fadeIn 0.2s ease',
        }}>
          {t.text}
        </div>
      ))}
      <style>{`@keyframes fadeIn { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }`}</style>
    </div>
  )
}
