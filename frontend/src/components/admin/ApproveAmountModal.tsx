import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Check, X } from 'lucide-react';

import { formatNumber } from '@/lib/utils';

interface Props {
  open: boolean;
  userName: string;
  initialAmount?: number;
  busy?: boolean;
  onCancel: () => void;
  onConfirm: (amount: number) => void;
}

const QUICK = [10000, 20000, 50000, 100000, 200000, 500000];

export function ApproveAmountModal({
  open,
  userName,
  initialAmount,
  busy,
  onCancel,
  onConfirm,
}: Props) {
  const { t } = useTranslation();
  const [raw, setRaw] = useState('');

  useEffect(() => {
    if (open) {
      setRaw(initialAmount && initialAmount > 0 ? String(initialAmount) : '');
    }
  }, [open, initialAmount]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onCancel();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onCancel]);

  if (!open) return null;

  const amount = Number(raw.replace(/[^\d]/g, '')) || 0;
  const valid = amount > 0;

  return (
    <div
      className="fixed inset-0 z-[80] grid place-items-center p-4 bg-black/50 backdrop-blur-sm animate-fade-in"
      onClick={onCancel}
    >
      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (valid) onConfirm(amount);
        }}
        onClick={(e) => e.stopPropagation()}
        className="bg-white w-full max-w-md rounded-2xl shadow-2xl p-5 sm:p-6"
      >
        <div className="flex items-start gap-3 mb-4">
          <div className="w-10 h-10 grid place-items-center rounded-xl bg-emerald-100 text-emerald-600 shrink-0">
            <Check size={18} />
          </div>
          <div className="min-w-0 flex-1">
            <h3 className="text-base font-bold text-slate-900">
              {t('admin.pay.approveTitle')}
            </h3>
            <p className="text-sm text-slate-500 truncate">{userName}</p>
          </div>
          <button
            type="button"
            onClick={onCancel}
            className="text-slate-400 hover:text-slate-600 shrink-0"
          >
            <X size={18} />
          </button>
        </div>

        <p className="text-sm text-slate-600 mb-3">
          {t('admin.pay.amountHint')}
        </p>

        <div className="relative mb-2">
          <input
            type="text"
            inputMode="numeric"
            value={raw ? formatNumber(amount) : ''}
            onChange={(e) => setRaw(e.target.value)}
            placeholder="0"
            autoFocus
            className="w-full text-3xl font-bold tabular-nums text-center px-4 py-5 border border-slate-300 rounded-xl bg-slate-50 focus:bg-white focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500 outline-none"
          />
          <span className="absolute right-4 top-1/2 -translate-y-1/2 text-slate-400 text-sm">so'm</span>
        </div>

        <div className="grid grid-cols-3 gap-1.5 mb-5">
          {QUICK.map((v) => (
            <button
              key={v}
              type="button"
              onClick={() => setRaw(String(v))}
              className="px-2 py-1.5 rounded-lg text-xs border border-slate-200 hover:bg-slate-50 text-slate-600 tabular-nums"
            >
              {formatNumber(v)}
            </button>
          ))}
        </div>

        <div className="flex gap-2">
          <button
            type="button"
            onClick={onCancel}
            className="flex-1 px-4 py-2.5 rounded-xl border border-slate-300 hover:bg-slate-50 font-medium text-sm text-slate-700"
          >
            {t('admin.cards.cancel')}
          </button>
          <button
            type="submit"
            disabled={busy || !valid}
            className="flex-1 px-4 py-2.5 rounded-xl bg-emerald-500 text-white font-semibold hover:bg-emerald-600 disabled:opacity-50 text-sm"
          >
            {busy ? '...' : t('admin.pay.approveAndCredit', { amount: formatNumber(amount) })}
          </button>
        </div>
      </form>
    </div>
  );
}
