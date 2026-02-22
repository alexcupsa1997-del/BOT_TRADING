import { useUIStore, type Toast as ToastType } from '../../store/uiStore';
import { X, CheckCircle, AlertTriangle, XCircle, Info } from 'lucide-react';

const iconMap = {
  success: <CheckCircle size={16} className="text-[var(--accent-green)]" />,
  error: <XCircle size={16} className="text-[var(--accent-red)]" />,
  warning: <AlertTriangle size={16} className="text-[var(--accent-yellow)]" />,
  info: <Info size={16} className="text-[var(--accent-blue)]" />,
};

const borderMap = {
  success: 'border-l-[var(--accent-green)]',
  error: 'border-l-[var(--accent-red)]',
  warning: 'border-l-[var(--accent-yellow)]',
  info: 'border-l-[var(--accent-blue)]',
};

function ToastItem({ toast }: { toast: ToastType }) {
  const removeToast = useUIStore((s) => s.removeToast);

  return (
    <div
      className={`glass-card p-3 pl-4 border-l-3 ${borderMap[toast.type]} min-w-72 max-w-96 animate-slide-in flex items-start gap-3`}
      style={{ borderLeftWidth: '3px', borderLeftStyle: 'solid' }}
    >
      <div className="mt-0.5">{iconMap[toast.type]}</div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-[var(--text-primary)]">{toast.title}</p>
        {toast.message && (
          <p className="text-xs text-[var(--text-secondary)] mt-0.5">{toast.message}</p>
        )}
      </div>
      <button
        onClick={() => removeToast(toast.id)}
        className="text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors"
      >
        <X size={14} />
      </button>
    </div>
  );
}

export default function ToastContainer() {
  const toasts = useUIStore((s) => s.toasts);

  if (toasts.length === 0) return null;

  return (
    <div className="toast-container">
      {toasts.map((toast) => (
        <ToastItem key={toast.id} toast={toast} />
      ))}
    </div>
  );
}
