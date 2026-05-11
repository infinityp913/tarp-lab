import { T } from '../tokens'

interface Props {
  message: string
  onConfirm: () => void
  onCancel: () => void
}

export function ConfirmationModal({ message, onConfirm, onCancel }: Props) {
  return (
    <div style={overlay}>
      <div style={dialog}>
        <h3 style={{ margin: '0 0 12px', fontSize: 18, color: T.text }}>Confirm Step</h3>
        <p style={{ margin: '0 0 24px', color: T.textSub, lineHeight: 1.5 }}>{message}</p>
        <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end' }}>
          <button onClick={onCancel} style={btnSecondary}>No, cancel</button>
          <button onClick={onConfirm} style={btnPrimary}>Yes, proceed</button>
        </div>
      </div>
    </div>
  )
}

const overlay: React.CSSProperties = {
  position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.65)',
  display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000,
}
const dialog: React.CSSProperties = {
  background: T.surface, borderRadius: 12, padding: 28, width: 420,
  boxShadow: '0 8px 40px rgba(0,0,0,0.5)', border: `1px solid ${T.border}`,
}
const btnPrimary: React.CSSProperties = {
  padding: '8px 20px', borderRadius: 6, border: 'none', cursor: 'pointer',
  background: T.accent, color: '#fff', fontWeight: 600, fontSize: 14,
}
const btnSecondary: React.CSSProperties = {
  padding: '8px 20px', borderRadius: 6, border: `1px solid ${T.border}`,
  cursor: 'pointer', background: T.surface, color: T.textSub, fontWeight: 600, fontSize: 14,
}
