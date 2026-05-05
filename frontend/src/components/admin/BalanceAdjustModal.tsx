import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Wallet, X, Plus, Minus } from 'lucide-react';

import { formatNumber } from '@/lib/utils';

interface Props {
  open: boolean;
  userName: string;
  currentBalance?: number;
  busy?: boolean;
  onCancel: () => void;
  onSubmit: (delta: number) => void;
}

const QUICK = [10000, 50000, 100000, 500000];

export function BalanceAdjustModal({
  open,
  userName,
  currentBalance,
  busy,
  onCancel,
  onSubmit,
}: Props) {
  const { t } = useTranslation();
  const [direction, setDirection] = useState<'add' | 'sub'>('add');
  const [raw, setRaw] = useState('');

  useEffect(() => {
    if (open) {
      setDirection('add');
      setRaw('');
    }
  }, [open]);

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
  const delta = direction === 'add' ? amount : -amount;
  const newBalance = currentBalance !== undefined ? currentBalance + delta : null;

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!amount) return;
    onSubmit(delta);
  }

  return (
    <div
      className="fixed inset-0 z-[80] grid place-items-center p-4 bg-black/50 backdrop-blur-sm animate-fade-in"
      onClick={onCancel}
    >
      <form
        onSubmit={submit}
        onClick={(e) => e.stopPropagation()}
        className="bg-white w-full max-w-md rounded-2xl shadow-2xl p-5 sm:p-6"
      >
        <div className="flex items-start gap-3 mb-4">
          <div className="w-10 h-10 grid place-items-center rounded-xl bg-brand-100 text-brand-600 shrink-0">
            <Wallet size={18} />
          </div>
          <div className="min-w-0 flex-1">
            <h3 className="text-base font-bold text-slate-900">
              {t('admin.users.adjustBalance')}
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

        {currentBalance !== undefined && (
          <div className="px-3 py-2 mb-3 rounded-xl bg-slate-50 text-sm text-slate-600 flex justify-between">
            <span>{t('admin.users.detail.balance')}</span>
            <span className="font-semibold tabular-nums">
              {formatNumber(currentBalance)} so'm
            </span>
          </div>
        )}

        {/* Direction toggle */}
        <div className="grid grid-cols-2 gap-2 mb-3">
          <button
            type="button"
            onClick={() => setDirection('add')}
            className={
              'flex items-center justify-center gap-2 py-2.5 rounded-xl font-medium text-sm border transition ' +
              (direction === 'add'
                ? 'bg-emerald-500 text-white border-emerald-500'
                : 'border-slate-300 text-slate-700 hover:bg-slate-50')
            }
          >
            <Plus size={15} /> {t('admin.balance.add')}
          </button>
          <button
            type="button"
            onClick={() => setDirection('sub')}
            className={
              'flex items-center justify-center gap-2 py-2.5 rounded-xl font-medium text-sm border transition ' +
              (direction === 'sub'
                ? 'bg-rose-500 text-white border-rose-500'
                : 'border-slate-300 text-slate-700 hover:bg-slate-50')
            }
          >
            <Minus size={15} /> {t('admin.balance.subtract')}
          </button>
        </div>

        {/* Amount input */}
        <div className="relative mb-2">
          <input
            type="text"
            inputMode="numeric"
            value={raw ? formatNumber(amount) : ''}
            onChange={(e) => setRaw(e.target.value)}
            placeholder="0"
            autoFocus
            className="w-full text-2xl font-bold tabular-nums text-center px-4 py-4 border border-slate-300 rounded-xl bg-slate-50 focus:bg-white focus:ring-2 focus:ring-brand-500 focus:border-brand-500 outline-none"
          />
          <span className="absolute right-4 top-1/2 -translate-y-1/2 text-slate-400 text-sm">so'm</span>
        </div>

        {/* Quick amounts */}
        <div className="grid grid-cols-4 gap-1.5 mb-3">
          {QUICK.map((v) => (
            <button
              key={v}
              type="button"
              onClick={() => setRaw(String(v))}
              className="px-2 py-1.5 rounded-lg text-xs border border-slate-200 hover:bg-slate-50 text-slate-600 tabular-nums"
            >
              {v >= 1000 ? `${v / 1000}K` : v}
            </button>
          ))}
        </div>

        {/* New balance preview */}
        {newBalance !== null && amount > 0 && (
          <div className="px-3 py-2 mb-4 rounded-xl bg-brand-50 border border-brand-100 text-sm flex justify-between">
            <span className="text-slate-600">{t('admin.balance.afterChange')}</span>
            <span
              className={
                'font-bold tabular-nums ' +
                (newBalance < 0 ? 'text-rose-600' : 'text-brand-700')
              }
            >
              {formatNumber(newBalance)} so'm
            </span>
          </div>
        )}

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
            disabled={busy || !amount}
            className={
              'flex-1 px-4 py-2.5 rounded-xl font-medium text-sm text-white disabled:opacity-50 ' +
              (direction === 'add'
                ? 'bg-emerald-500 hover:bg-emerald-600'
                : 'bg-rose-500 hover:bg-rose-600')
            }
          >
            {busy ? '...' : t('admin.balance.confirm')}
          </button>
        </div>
      </form>
    </div>
  );
}
