import { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { X, ShieldCheck, ShieldOff, Crown, KeyRound } from 'lucide-react';
import toast from 'react-hot-toast';

import { apiGet, apiPost } from '@/lib/api';
import { formatNumber } from '@/lib/utils';
import { StatusBadge } from '@/components/StatusBadge';
import { CredentialsRevealModal } from '@/components/admin/CredentialsRevealModal';
import { ConfirmDialog } from '@/components/admin/ConfirmDialog';

interface OrderRow {
  id: number;
  doc_type: string;
  title: string;
  status: string;
  length: string;
  price: number;
  is_free: boolean;
  created_at: string;
}

interface PaymentRow {
  id: number;
  amount: number;
  status: string;
  invoice_id: string;
  created_at: string;
}

interface Detail {
  user: {
    id: string;
    username: string;
    full_name: string;
    balance: number;
    is_blocked: boolean;
    role: string;
    language: string;
    plan: string;
    has_used_free_trial: boolean;
    created_at: string;
    last_active: string;
  };
  stats: {
    total_orders: number;
    completed_orders: number;
    total_payments: number;
    total_spent: number;
  };
}

interface PageResp<T> {
  total: number;
  items: T[];
}

interface Props {
  userId: string;
  isSuperadmin: boolean;
  onClose: () => void;
  onChange?: () => void;
}

const PAGE_SIZE = 20;

export function UserDetailDrawer({ userId, isSuperadmin, onClose, onChange }: Props) {
  const { t, i18n } = useTranslation();
  const [data, setData] = useState<Detail | null>(null);
  const [tab, setTab] = useState<'orders' | 'payments'>('orders');
  const [busy, setBusy] = useState(false);
  const [creds, setCreds] = useState<{ username: string; password: string } | null>(null);
  const [confirmReset, setConfirmReset] = useState(false);

  const [ordersData, setOrdersData] = useState<PageResp<OrderRow> | null>(null);
  const [ordersPage, setOrdersPage] = useState(0);
  const [paymentsData, setPaymentsData] = useState<PageResp<PaymentRow> | null>(null);
  const [paymentsPage, setPaymentsPage] = useState(0);

  useEffect(() => {
    apiGet<Detail>(`/admin/users/${userId}/detail`).then(setData);
  }, [userId]);

  useEffect(() => {
    apiGet<PageResp<OrderRow>>(
      `/admin/users/${userId}/orders?limit=${PAGE_SIZE}&offset=${ordersPage * PAGE_SIZE}`,
    ).then(setOrdersData);
  }, [userId, ordersPage]);

  useEffect(() => {
    apiGet<PageResp<PaymentRow>>(
      `/admin/users/${userId}/payments?limit=${PAGE_SIZE}&offset=${paymentsPage * PAGE_SIZE}`,
    ).then(setPaymentsData);
  }, [userId, paymentsPage]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      window.removeEventListener('keydown', onKey);
      document.body.style.overflow = prev;
    };
  }, [onClose]);

  async function changeRole(role: 'user' | 'admin' | 'superadmin') {
    if (!data) return;
    setBusy(true);
    try {
      const r = await apiPost<{
        role: string;
        credentials?: { username: string; password: string } | null;
      }>(`/admin/users/${data.user.id}/role`, { role });
      toast.success(t('admin.users.roleUpdated'));
      setData({ ...data, user: { ...data.user, role } });
      if (r.credentials) {
        setCreds(r.credentials);
      }
      onChange?.();
    } catch (e: any) {
      toast.error(e?.response?.data?.message || 'Xato');
    } finally {
      setBusy(false);
    }
  }

  async function performResetPassword() {
    if (!data) return;
    setConfirmReset(false);
    setBusy(true);
    try {
      const r = await apiPost<{ username: string; password: string }>(
        `/admin/users/${data.user.id}/reset-password`,
        {},
      );
      toast.success(t('admin.users.passwordReset'));
      setCreds(r);
    } catch (e: any) {
      toast.error(e?.response?.data?.message || 'Xato');
    } finally {
      setBusy(false);
    }
  }

  const ordersTotalPages = useMemo(
    () => (ordersData ? Math.max(1, Math.ceil(ordersData.total / PAGE_SIZE)) : 1),
    [ordersData],
  );
  const paymentsTotalPages = useMemo(
    () => (paymentsData ? Math.max(1, Math.ceil(paymentsData.total / PAGE_SIZE)) : 1),
    [paymentsData],
  );

  const fmtDate = (s: string) =>
    new Date(s).toLocaleString(i18n.language === 'ru' ? 'ru-RU' : 'uz-UZ', {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });

  return (
    <div className="fixed inset-0 z-[60]">
      <div
        className="absolute inset-0 bg-black/50 backdrop-blur-sm animate-fade-in"
        onClick={onClose}
      />
      <aside className="absolute top-0 right-0 h-full w-full sm:w-[600px] max-w-[100vw] bg-white shadow-2xl flex flex-col animate-slide-in-right">
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-200">
          <h2 className="font-bold text-slate-900">{t('admin.users.detail.title')}</h2>
          <button
            onClick={onClose}
            className="w-8 h-8 grid place-items-center rounded-lg hover:bg-slate-100"
          >
            <X size={18} />
          </button>
        </div>

        {!data ? (
          <div className="flex-1 grid place-items-center text-slate-400 text-sm">
            {t('common.loading')}
          </div>
        ) : (
          <div className="flex-1 overflow-y-auto">
            <div className="px-5 py-4 bg-gradient-to-br from-slate-50 to-white border-b border-slate-100">
              <div className="flex items-start justify-between gap-3 mb-3">
                <div>
                  <div className="text-lg font-bold text-slate-900">
                    {data.user.full_name || data.user.username || `#${data.user.id}`}
                  </div>
                  <div className="text-xs text-slate-500 mt-0.5">
                    {data.user.username && `@${data.user.username} · `}#{data.user.id}
                  </div>
                </div>
                <span
                  className={
                    'inline-block px-2 py-0.5 rounded-full text-[11px] font-medium border ' +
                    (data.user.role === 'superadmin'
                      ? 'bg-rose-100 text-rose-700 border-rose-200'
                      : data.user.role === 'admin'
                        ? 'bg-violet-100 text-violet-700 border-violet-200'
                        : 'bg-slate-100 text-slate-600 border-slate-200')
                  }
                >
                  {data.user.role}
                </span>
              </div>
              <div className="grid grid-cols-3 gap-2">
                <Stat label={t('admin.users.detail.balance')} value={`${formatNumber(data.user.balance)}`} />
                <Stat label={t('admin.users.detail.totalSpent')} value={`${formatNumber(data.stats.total_spent)}`} />
                <Stat label={t('admin.users.detail.completed')} value={`${data.stats.completed_orders}/${data.stats.total_orders}`} />
              </div>

              {isSuperadmin && (
                <div className="mt-4 flex flex-wrap gap-2">
                  {data.user.role === 'user' && (
                    <button
                      disabled={busy}
                      onClick={() => changeRole('admin')}
                      className="inline-flex items-center gap-2 px-3 py-2 rounded-xl border border-violet-300 text-violet-700 bg-violet-50 hover:bg-violet-100 text-sm font-medium disabled:opacity-50"
                    >
                      <ShieldCheck size={15} /> {t('admin.users.promoteAdmin')}
                    </button>
                  )}
                  {data.user.role !== 'superadmin' && (
                    <button
                      disabled={busy}
                      onClick={() => changeRole('superadmin')}
                      className="inline-flex items-center gap-2 px-3 py-2 rounded-xl border border-rose-300 text-rose-700 bg-rose-50 hover:bg-rose-100 text-sm font-medium disabled:opacity-50"
                    >
                      <Crown size={15} /> {t('admin.users.promoteSuperadmin')}
                    </button>
                  )}
                  {data.user.role !== 'user' && (
                    <button
                      disabled={busy}
                      onClick={() => changeRole('user')}
                      className="inline-flex items-center gap-2 px-3 py-2 rounded-xl border border-slate-300 text-slate-700 bg-slate-50 hover:bg-slate-100 text-sm font-medium disabled:opacity-50"
                    >
                      <ShieldOff size={15} /> {t('admin.users.demoteAdmin')}
                    </button>
                  )}
                  {(data.user.role === 'admin' || data.user.role === 'superadmin') && (
                    <button
                      disabled={busy}
                      onClick={() => setConfirmReset(true)}
                      className="inline-flex items-center gap-2 px-3 py-2 rounded-xl border border-amber-300 text-amber-700 bg-amber-50 hover:bg-amber-100 text-sm font-medium disabled:opacity-50"
                    >
                      <KeyRound size={15} /> {t('admin.users.resetPassword')}
                    </button>
                  )}
                </div>
              )}
            </div>

            {/* Tabs */}
            <div className="px-5 pt-4 border-b border-slate-200 flex gap-1">
              <TabBtn active={tab === 'orders'} onClick={() => setTab('orders')}>
                {t('admin.users.detail.ordersTab', { count: data.stats.total_orders })}
              </TabBtn>
              <TabBtn active={tab === 'payments'} onClick={() => setTab('payments')}>
                {t('admin.users.detail.paymentsTab', { count: data.stats.total_payments })}
              </TabBtn>
            </div>

            {/* Tab content */}
            <div className="px-5 py-4">
              {tab === 'orders' && (
                !ordersData ? (
                  <Empty text={t('common.loading')} />
                ) : ordersData.items.length === 0 ? (
                  <Empty text={t('admin.users.detail.noOrders')} />
                ) : (
                  <>
                    <ul className="space-y-2">
                      {ordersData.items.map((o) => (
                        <li
                          key={o.id}
                          className="flex items-start justify-between gap-3 p-3 rounded-xl border border-slate-200 hover:bg-slate-50/60 transition"
                        >
                          <div className="min-w-0 flex-1">
                            <div className="flex items-center gap-2 mb-0.5">
                              <span className="text-xs px-1.5 py-0.5 rounded bg-slate-100 text-slate-600">
                                {t(`docTypes.${o.doc_type}`, o.doc_type)}
                              </span>
                              {o.is_free && (
                                <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-700 font-medium">
                                  {t('admin.free')}
                                </span>
                              )}
                            </div>
                            <div className="text-sm font-medium text-slate-900 truncate">
                              {o.title}
                            </div>
                            <div className="text-[11px] text-slate-500 mt-0.5">
                              {fmtDate(o.created_at)} · {o.length} {t('orders.pages')}
                            </div>
                          </div>
                          <div className="text-right shrink-0">
                            <StatusBadge status={o.status} />
                            <div className="text-xs text-slate-600 mt-1 tabular-nums">
                              {formatNumber(o.price)}
                            </div>
                          </div>
                        </li>
                      ))}
                    </ul>
                    {ordersData.total > PAGE_SIZE && (
                      <Pagination
                        page={ordersPage}
                        totalPages={ordersTotalPages}
                        onPrev={() => setOrdersPage((p) => Math.max(0, p - 1))}
                        onNext={() => setOrdersPage((p) => p + 1)}
                        label={t('admin.users.pageOf', { current: ordersPage + 1, total: ordersTotalPages })}
                      />
                    )}
                  </>
                )
              )}

              {tab === 'payments' && (
                !paymentsData ? (
                  <Empty text={t('common.loading')} />
                ) : paymentsData.items.length === 0 ? (
                  <Empty text={t('admin.users.detail.noPayments')} />
                ) : (
                  <>
                    <ul className="space-y-2">
                      {paymentsData.items.map((p) => (
                        <li
                          key={p.id}
                          className="flex items-center justify-between gap-3 p-3 rounded-xl border border-slate-200"
                        >
                          <div className="min-w-0">
                            <div className="text-sm font-medium text-slate-900 tabular-nums">
                              {formatNumber(p.amount)} so'm
                            </div>
                            <div className="text-[11px] text-slate-500 mt-0.5">
                              {fmtDate(p.created_at)} · #{p.invoice_id}
                            </div>
                          </div>
                          <PaymentStatus status={p.status} />
                        </li>
                      ))}
                    </ul>
                    {paymentsData.total > PAGE_SIZE && (
                      <Pagination
                        page={paymentsPage}
                        totalPages={paymentsTotalPages}
                        onPrev={() => setPaymentsPage((p) => Math.max(0, p - 1))}
                        onNext={() => setPaymentsPage((p) => p + 1)}
                        label={t('admin.users.pageOf', { current: paymentsPage + 1, total: paymentsTotalPages })}
                      />
                    )}
                  </>
                )
              )}
            </div>
          </div>
        )}
      </aside>

      <CredentialsRevealModal
        open={!!creds}
        username={creds?.username || ''}
        password={creds?.password || ''}
        onClose={() => setCreds(null)}
      />

      <ConfirmDialog
        open={confirmReset}
        title={t('admin.users.resetPassword')}
        message={t('admin.users.resetPasswordConfirm')}
        confirmLabel={t('admin.users.resetPassword')}
        cancelLabel={t('admin.cards.cancel')}
        tone="danger"
        onCancel={() => setConfirmReset(false)}
        onConfirm={performResetPassword}
      />
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-white rounded-xl border border-slate-200 p-3">
      <div className="text-[10px] uppercase tracking-wide text-slate-400">{label}</div>
      <div className="text-sm font-bold text-slate-900 mt-0.5 truncate">{value}</div>
    </div>
  );
}

function TabBtn({
  active,
  children,
  onClick,
}: {
  active: boolean;
  children: React.ReactNode;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={
        'px-4 py-2 text-sm font-medium border-b-2 transition -mb-px ' +
        (active
          ? 'border-brand-500 text-brand-700'
          : 'border-transparent text-slate-500 hover:text-slate-900')
      }
    >
      {children}
    </button>
  );
}

function Empty({ text }: { text: string }) {
  return <div className="text-center text-sm text-slate-400 py-8">{text}</div>;
}

function Pagination({
  page,
  totalPages,
  onPrev,
  onNext,
  label,
}: {
  page: number;
  totalPages: number;
  onPrev: () => void;
  onNext: () => void;
  label: string;
}) {
  return (
    <div className="flex items-center justify-between mt-3 text-sm">
      <div className="text-slate-500">{label}</div>
      <div className="flex gap-2">
        <button
          disabled={page === 0}
          onClick={onPrev}
          className="px-3 py-1.5 rounded-lg border border-slate-300 disabled:opacity-40 hover:bg-slate-50 bg-white"
        >
          ←
        </button>
        <button
          disabled={page + 1 >= totalPages}
          onClick={onNext}
          className="px-3 py-1.5 rounded-lg border border-slate-300 disabled:opacity-40 hover:bg-slate-50 bg-white"
        >
          →
        </button>
      </div>
    </div>
  );
}

function PaymentStatus({ status }: { status: string }) {
  const map: Record<string, string> = {
    approved: 'bg-emerald-100 text-emerald-700 border-emerald-200',
    pending:  'bg-amber-100 text-amber-700 border-amber-200',
    rejected: 'bg-rose-100 text-rose-700 border-rose-200',
  };
  return (
    <span
      className={`text-[11px] px-2 py-0.5 rounded-full font-medium border ${map[status] ?? map.pending}`}
    >
      {status}
    </span>
  );
}
