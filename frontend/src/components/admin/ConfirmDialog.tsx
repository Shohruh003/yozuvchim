import { useEffect } from 'react';
import { AlertTriangle, X } from 'lucide-react';

interface Props {
  open: boolean;
  title: string;
  message?: string;
  confirmLabel?: string;
  cancelLabel?: string;
  tone?: 'default' | 'danger';
  onConfirm: () => void;
  onCancel: () => void;
}

export function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel = 'OK',
  cancelLabel = 'Bekor qilish',
  tone = 'default',
  onConfirm,
  onCancel,
}: Props) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onCancel();
      if (e.key === 'Enter') onConfirm();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onCancel, onConfirm]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-[80] grid place-items-center p-4 bg-black/50 backdrop-blur-sm animate-fade-in"
      onClick={onCancel}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="bg-white w-full max-w-sm rounded-2xl shadow-2xl p-5 sm:p-6"
      >
        <div className="flex items-start gap-3 mb-3">
          {tone === 'danger' && (
            <div className="w-10 h-10 grid place-items-center rounded-xl bg-rose-100 text-rose-600 shrink-0">
              <AlertTriangle size={18} />
            </div>
          )}
          <div className="min-w-0 flex-1">
            <h3 className="text-base font-bold text-slate-900">{title}</h3>
            {message && <p className="text-sm text-slate-600 mt-1">{message}</p>}
          </div>
          <button
            onClick={onCancel}
            className="text-slate-400 hover:text-slate-600 shrink-0"
          >
            <X size={18} />
          </button>
        </div>

        <div className="flex gap-2 mt-4">
          <button
            onClick={onCancel}
            className="flex-1 px-4 py-2.5 rounded-xl border border-slate-300 hover:bg-slate-50 font-medium text-sm text-slate-700"
          >
            {cancelLabel}
          </button>
          <button
            onClick={onConfirm}
            className={
              'flex-1 px-4 py-2.5 rounded-xl font-medium text-sm text-white ' +
              (tone === 'danger'
                ? 'bg-rose-500 hover:bg-rose-600'
                : 'bg-brand-500 hover:bg-brand-600')
            }
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
