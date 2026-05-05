import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import toast from 'react-hot-toast';
import { Plus, Pencil, Trash2, CreditCard, Power } from 'lucide-react';

import { apiGet, apiPost } from '@/lib/api';
import { ConfirmDialog } from '@/components/admin/ConfirmDialog';

interface Card {
  id: number;
  number: string;
  holder: string;
  bank: string;
  is_active: boolean;
  sort_order: number;
  created_at: string;
}

interface FormData {
  number: string;
  holder: string;
  bank: string;
  is_active: boolean;
  sort_order: number;
}

const EMPTY_FORM: FormData = {
  number: '',
  holder: '',
  bank: '',
  is_active: true,
  sort_order: 0,
};

export default function AdminCardsPage() {
  const { t } = useTranslation();
  const [cards, setCards] = useState<Card[] | null>(null);
  const [editing, setEditing] = useState<Card | null>(null);
  const [creating, setCreating] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<Card | null>(null);

  function reload() {
    apiGet<Card[]>('/admin/cards').then(setCards).catch(() => setCards([]));
  }
  useEffect(reload, []);

  async function toggleActive(c: Card) {
    try {
      await apiPost(`/admin/cards/${c.id}`, { is_active: !c.is_active });
      reload();
    } catch (e: any) {
      toast.error(e?.response?.data?.message || 'Xato');
    }
  }

  async function performDelete() {
    if (!deleteTarget) return;
    try {
      await apiPost(`/admin/cards/${deleteTarget.id}/delete`, {});
      toast.success(t('admin.cards.deleted'));
      reload();
    } catch (e: any) {
      toast.error(e?.response?.data?.message || 'Xato');
    } finally {
      setDeleteTarget(null);
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold text-slate-900">{t('admin.cards.title')}</h1>
          <p className="text-sm text-slate-500 mt-0.5">{t('admin.cards.subtitle')}</p>
        </div>
        <button
          onClick={() => setCreating(true)}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-brand-500 text-white font-medium hover:bg-brand-600 text-sm"
        >
          <Plus size={16} /> {t('admin.cards.add')}
        </button>
      </div>

      {!cards ? (
        <div className="text-slate-400 text-sm">{t('common.loading')}</div>
      ) : cards.length === 0 ? (
        <div className="bg-white rounded-2xl border border-slate-200 p-10 text-center">
          <CreditCard size={36} className="mx-auto text-slate-300 mb-3" />
          <p className="text-slate-500 mb-4">{t('admin.cards.empty')}</p>
          <button
            onClick={() => setCreating(true)}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-brand-500 text-white font-medium hover:bg-brand-600 text-sm"
          >
            <Plus size={16} /> {t('admin.cards.addFirst')}
          </button>
        </div>
      ) : (
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3 sm:gap-4">
          {cards.map((c) => (
            <article
              key={c.id}
              className={
                'rounded-2xl border p-5 relative overflow-hidden transition ' +
                (c.is_active
                  ? 'bg-gradient-to-br from-indigo-500 via-purple-600 to-fuchsia-600 text-white border-transparent shadow-lg'
                  : 'bg-slate-100 text-slate-500 border-slate-200')
              }
            >
              <div className="flex items-start justify-between gap-3">
                <CreditCard size={28} className="opacity-80" />
                {!c.is_active && (
                  <span className="text-[10px] uppercase tracking-wide font-semibold px-2 py-0.5 rounded-full bg-slate-300/60 text-slate-700">
                    {t('admin.cards.inactive')}
                  </span>
                )}
              </div>
              <div className="mt-6">
                <div className={'text-xs ' + (c.is_active ? 'text-white/70' : 'text-slate-400')}>
                  {c.bank || t('admin.cards.bankLabel')}
                </div>
                <div className="text-xl sm:text-2xl font-mono font-bold mt-1 tracking-wider">
                  {formatCard(c.number)}
                </div>
              </div>
              <div className="mt-4 flex items-end justify-between gap-3">
                <div className="min-w-0">
                  <div className={'text-[10px] uppercase ' + (c.is_active ? 'text-white/60' : 'text-slate-400')}>
                    {t('admin.cards.holder')}
                  </div>
                  <div className="font-semibold truncate">{c.holder}</div>
                </div>
                <div className="flex gap-1.5 shrink-0">
                  <ActionBtn
                    title={c.is_active ? t('admin.cards.deactivate') : t('admin.cards.activate')}
                    light={c.is_active}
                    onClick={() => toggleActive(c)}
                  >
                    <Power size={14} />
                  </ActionBtn>
                  <ActionBtn
                    title={t('admin.cards.edit')}
                    light={c.is_active}
                    onClick={() => setEditing(c)}
                  >
                    <Pencil size={14} />
                  </ActionBtn>
                  <ActionBtn
                    title={t('admin.cards.delete')}
                    light={c.is_active}
                    onClick={() => setDeleteTarget(c)}
                  >
                    <Trash2 size={14} />
                  </ActionBtn>
                </div>
              </div>
            </article>
          ))}
        </div>
      )}

      {(creating || editing) && (
        <CardModal
          initial={editing ?? EMPTY_FORM}
          mode={editing ? 'edit' : 'create'}
          onClose={() => {
            setCreating(false);
            setEditing(null);
          }}
          onSaved={() => {
            setCreating(false);
            setEditing(null);
            reload();
          }}
        />
      )}

      <ConfirmDialog
        open={!!deleteTarget}
        title={t('admin.cards.delete')}
        message={
          deleteTarget ? t('admin.cards.confirmDelete', { number: deleteTarget.number }) : ''
        }
        confirmLabel={t('admin.cards.delete')}
        cancelLabel={t('admin.cards.cancel')}
        tone="danger"
        onCancel={() => setDeleteTarget(null)}
        onConfirm={performDelete}
      />
    </div>
  );
}

function formatCard(n: string) {
  return n.replace(/\s+/g, '').replace(/(.{4})/g, '$1 ').trim();
}

function ActionBtn({
  children,
  onClick,
  title,
  light,
}: {
  children: React.ReactNode;
  onClick: () => void;
  title: string;
  light: boolean;
}) {
  return (
    <button
      onClick={onClick}
      title={title}
      className={
        'w-8 h-8 grid place-items-center rounded-lg transition ' +
        (light
          ? 'bg-white/15 hover:bg-white/25 text-white'
          : 'bg-white text-slate-600 hover:bg-slate-200 border border-slate-200')
      }
    >
      {children}
    </button>
  );
}

function CardModal({
  initial,
  mode,
  onClose,
  onSaved,
}: {
  initial: FormData | Card;
  mode: 'create' | 'edit';
  onClose: () => void;
  onSaved: () => void;
}) {
  const { t } = useTranslation();
  const [form, setForm] = useState<FormData>({
    number: initial.number,
    holder: initial.holder,
    bank: initial.bank,
    is_active: initial.is_active,
    sort_order: initial.sort_order,
  });
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!form.number.trim() || !form.holder.trim()) {
      toast.error(t('admin.cards.requiredFields'));
      return;
    }
    setBusy(true);
    try {
      if (mode === 'edit' && 'id' in initial) {
        await apiPost(`/admin/cards/${initial.id}`, form);
        toast.success(t('admin.cards.updated'));
      } else {
        await apiPost('/admin/cards', form);
        toast.success(t('admin.cards.added'));
      }
      onSaved();
    } catch (e: any) {
      toast.error(e?.response?.data?.message || 'Xato');
    } finally {
      setBusy(false);
    }
  }

  return (
    <div
      className="fixed inset-0 z-[60] grid place-items-center p-4 bg-black/50 backdrop-blur-sm animate-fade-in"
      onClick={onClose}
    >
      <form
        onSubmit={submit}
        onClick={(e) => e.stopPropagation()}
        className="bg-white w-full max-w-md rounded-2xl shadow-2xl p-5 sm:p-6 space-y-4"
      >
        <h2 className="text-lg font-bold text-slate-900">
          {mode === 'edit' ? t('admin.cards.editTitle') : t('admin.cards.addTitle')}
        </h2>

        <Field label={t('admin.cards.number')}>
          <input
            value={form.number}
            onChange={(e) => setForm({ ...form, number: e.target.value })}
            placeholder="5614 6812 1506 0850"
            inputMode="numeric"
            className="w-full border border-slate-300 rounded-xl px-3 py-2.5 font-mono"
          />
        </Field>
        <Field label={t('admin.cards.holder')}>
          <input
            value={form.holder}
            onChange={(e) => setForm({ ...form, holder: e.target.value })}
            placeholder="Imomaliyev Abdurasul"
            className="w-full border border-slate-300 rounded-xl px-3 py-2.5"
          />
        </Field>
        <Field label={t('admin.cards.bankLabel') + ' (' + t('admin.cards.optional') + ')'}>
          <input
            value={form.bank}
            onChange={(e) => setForm({ ...form, bank: e.target.value })}
            placeholder="Humo / Uzcard / Visa"
            className="w-full border border-slate-300 rounded-xl px-3 py-2.5"
          />
        </Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label={t('admin.cards.sortOrder')}>
            <input
              type="number"
              value={form.sort_order}
              onChange={(e) => setForm({ ...form, sort_order: Number(e.target.value) || 0 })}
              className="w-full border border-slate-300 rounded-xl px-3 py-2.5"
            />
          </Field>
          <Field label={t('admin.cards.status')}>
            <label className="inline-flex items-center gap-2 mt-2">
              <input
                type="checkbox"
                checked={form.is_active}
                onChange={(e) => setForm({ ...form, is_active: e.target.checked })}
                className="w-4 h-4"
              />
              <span className="text-sm">{t('admin.cards.activeFlag')}</span>
            </label>
          </Field>
        </div>

        <div className="flex gap-2 pt-2">
          <button
            type="button"
            onClick={onClose}
            className="flex-1 px-4 py-2.5 rounded-xl border border-slate-300 hover:bg-slate-50 font-medium text-sm"
          >
            {t('admin.cards.cancel')}
          </button>
          <button
            type="submit"
            disabled={busy}
            className="flex-1 px-4 py-2.5 rounded-xl bg-brand-500 text-white font-medium hover:bg-brand-600 disabled:opacity-50 text-sm"
          >
            {busy ? '...' : mode === 'edit' ? t('admin.cards.save') : t('admin.cards.add')}
          </button>
        </div>
      </form>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="block text-xs uppercase tracking-wide text-slate-500 font-medium mb-1.5">
        {label}
      </label>
      {children}
    </div>
  );
}
