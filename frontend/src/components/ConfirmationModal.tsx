interface Props {
  message: string
  onConfirm: () => void
  onCancel: () => void
}

export function ConfirmationModal({ message, onConfirm, onCancel }: Props) {
  return (
    <div style={overlay}>
      <div style={dialog}>
        <h3 style={{ margin: '0 0 12px', fontSize: 18, color: '#1a1a2e' }}>Confirm Step</h3>
        <p style={{ margin: '0 0 24px', color: '#444', lineHeight: 1.5 }}>{message}</p>
        <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end' }}>
          <button onClick={onCancel} style={btnSecondary}>No, cancel</button>
          <button onClick={onConfirm} style={btnPrimary}>Yes, proceed</button>
        </div>
      </div>
    </div>
  )
}

const overlay: React.CSSProperties = {
  position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.45)',
  display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000,
}
const dialog: React.CSSProperties = {
  background: '#fff', borderRadius: 12, padding: 28, width: 420,
  boxShadow: '0 8px 40px rgba(0,0,0,0.2)',
}
const btnPrimary: React.CSSProperties = {
  padding: '8px 20px', borderRadius: 6, border: 'none', cursor: 'pointer',
  background: '#2563eb', color: '#fff', fontWeight: 600, fontSize: 14,
}
const btnSecondary: React.CSSProperties = {
  padding: '8px 20px', borderRadius: 6, border: '1px solid #d1d5db',
  cursor: 'pointer', background: '#fff', color: '#374151', fontWeight: 600, fontSize: 14,
}
