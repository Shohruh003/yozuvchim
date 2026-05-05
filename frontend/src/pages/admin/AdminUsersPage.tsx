import { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import toast from 'react-hot-toast';
import { Search, Ban, CheckCircle2, Wallet, Eye } from 'lucide-react';

import { apiGet, apiPost } from '@/lib/api';
import { formatNumber } from '@/lib/utils';
import { UserDetailDrawer } from '@/components/admin/UserDetailDrawer';
import { BalanceAdjustModal } from '@/components/admin/BalanceAdjustModal';
import { ConfirmDialog } from '@/components/admin/ConfirmDialog';

interface UserRow {
  id: string;
  username: string;
  full_name: string;
  balance: number;
  is_blocked: boolean;
  role: string;
  total_orders: number;
  total_spent: number;
  created_at: string;
}

interface UsersResp {
  total: number;
  items: UserRow[];
}

interface Me {
  id: string;
  role: string;
}

const PAGE_SIZE = 20;

export default function AdminUsersPage() {
  const { t, i18n } = useTranslation();
  const [search, setSearch] = useState('');
  const [debounced, setDebounced] = useState('');
  const [page, setPage] = useState(0);
  const [data, setData] = useState<UsersResp | null>(null);
  const [loading, setLoading] = useState(false);
  const [openId, setOpenId] = useState<string | null>(null);
  const [me, setMe] = useState<Me | null>(null);
  const [balanceTarget, setBalanceTarget] = useState<UserRow | null>(null);
  const [balanceBusy, setBalanceBusy] = useState(false);
  const [blockTarget, setBlockTarget] = useState<UserRow | null>(null);

  useEffect(() => {
    apiGet<Me>('/users/me').then(setMe).catch(() => null);
  }, []);

  // Debounce search
  useEffect(() => {
    const id = window.setTimeout(() => setDebounced(search.trim()), 350);
    return () => window.clearTimeout(id);
  }, [search]);

  useEffect(() => {
    setPage(0);
  }, [debounced]);

  useEffect(() => {
    setLoading(true);
    apiGet<UsersResp>(
      `/admin/users?limit=${PAGE_SIZE}&offset=${page * PAGE_SIZE}&search=${encodeURIComponent(debounced)}`,
    )
      .then(setData)
      .catch(() => null)
      .finally(() => setLoading(false));
  }, [page, debounced]);

  const totalPages = useMemo(
    () => (data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1),
    [data],
  );

  async function performBlock(u: UserRow) {
    try {
      await apiPost(`/admin/users/${u.id}/${u.is_blocked ? 'unblock' : 'block'}`, {});
      toast.success(u.is_blocked ? t('admin.users.unblocked') : t('admin.users.blocked'));
      setData((d) =>
        d
          ? {
              ...d,
              items: d.items.map((x) =>
                x.id === u.id ? { ...x, is_blocked: !u.is_blocked } : x,
              ),
            }
          : d,
      );
    } catch (e: any) {
      toast.error(e?.response?.data?.message || 'Xato');
    } finally {
      setBlockTarget(null);
    }
  }

  async function performBalance(delta: number) {
    if (!balanceTarget) return;
    const u = balanceTarget;
    setBalanceBusy(true);
    try {
      const r = await apiPost<{ balance: number }>(`/admin/users/${u.id}/balance`, { delta });
      toast.success(t('admin.users.balanceUpdated'));
      setData((d) =>
        d
          ? {
              ...d,
              items: d.items.map((x) =>
                x.id === u.id ? { ...x, balance: r.balance } : x,
              ),
            }
          : d,
      );
      setBalanceTarget(null);
    } catch (e: any) {
      toast.error(e?.response?.data?.message || 'Xato');
    } finally {
      setBalanceBusy(false);
    }
  }

  const fmtDate = (s: string) =>
    new Date(s).toLocaleDateString(i18n.language === 'ru' ? 'ru-RU' : 'uz-UZ', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold text-slate-900">
            {t('admin.users.title')}
          </h1>
          <p className="text-sm text-slate-500 mt-0.5">
            {data ? t('admin.users.totalCount', { count: data.total }) : ''}
          </p>
        </div>
        <div className="relative w-full sm:w-72">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder={t('admin.users.searchPlaceholder')}
            className="w-full pl-9 pr-3 py-2 border border-slate-300 rounded-xl text-sm bg-white focus:ring-2 focus:ring-brand-500 focus:border-brand-500 outline-none"
          />
        </div>
      </div>

      <div className="bg-white rounded-2xl border border-slate-200 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-slate-500 text-xs uppercase">
              <tr>
                <th className="text-left px-4 py-3 font-medium">{t('admin.users.col.user')}</th>
                <th className="text-left px-4 py-3 font-medium">{t('admin.users.col.role')}</th>
                <th className="text-right px-4 py-3 font-medium">{t('admin.users.col.balance')}</th>
                <th className="text-right px-4 py-3 font-medium">{t('admin.users.col.orders')}</th>
                <th className="text-right px-4 py-3 font-medium">{t('admin.users.col.spent')}</th>
                <th className="text-left px-4 py-3 font-medium">{t('admin.users.col.joined')}</th>
                <th className="text-right px-4 py-3 font-medium">{t('admin.users.col.actions')}</th>
              </tr>
            </thead>
            <tbody>
              {loading && !data && (
                <tr><td colSpan={7} className="px-4 py-8 text-center text-slate-400">{t('common.loading')}</td></tr>
              )}
              {data?.items.map((u) => (
                <tr key={u.id} className="border-t border-slate-100 hover:bg-slate-50/50">
                  <td className="px-4 py-3">
                    <button
                      onClick={() => setOpenId(u.id)}
                      className="text-left hover:text-brand-600 transition"
                    >
                      <div className="font-medium text-slate-900 truncate max-w-[200px]">
                        {u.full_name || u.username || `#${u.id}`}
                      </div>
                      <div className="text-xs text-slate-500">
                        {u.username ? `@${u.username}` : `#${u.id}`}
                      </div>
                    </button>
                  </td>
                  <td className="px-4 py-3">
                    <RoleBadge role={u.role} />
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums font-medium">
                    {formatNumber(u.balance)}
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums">{u.total_orders}</td>
                  <td className="px-4 py-3 text-right tabular-nums text-slate-600">
                    {formatNumber(u.total_spent)}
                  </td>
                  <td className="px-4 py-3 text-slate-600">{fmtDate(u.created_at)}</td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-1 justify-end">
                      <IconBtn title={t('admin.users.viewDetail')} onClick={() => setOpenId(u.id)}>
                        <Eye size={15} />
                      </IconBtn>
                      <IconBtn title={t('admin.users.adjustBalance')} onClick={() => setBalanceTarget(u)}>
                        <Wallet size={15} />
                      </IconBtn>
                      <IconBtn
                        title={u.is_blocked ? t('admin.users.unblock') : t('admin.users.block')}
                        onClick={() => setBlockTarget(u)}
                        tone={u.is_blocked ? 'emerald' : 'rose'}
                      >
                        {u.is_blocked ? <CheckCircle2 size={15} /> : <Ban size={15} />}
                      </IconBtn>
                    </div>
                  </td>
                </tr>
              ))}
              {data && data.items.length === 0 && (
                <tr><td colSpan={7} className="px-4 py-8 text-center text-slate-400">{t('admin.users.empty')}</td></tr>
              )}
            </tbody>
          </table>
        </div>

        {data && data.total > PAGE_SIZE && (
          <div className="flex items-center justify-between px-4 py-3 border-t border-slate-100 text-sm">
            <div className="text-slate-500">
              {t('admin.users.pageOf', { current: page + 1, total: totalPages })}
            </div>
            <div className="flex gap-2">
              <button
                disabled={page === 0}
                onClick={() => setPage((p) => Math.max(0, p - 1))}
                className="px-3 py-1.5 rounded-lg border border-slate-300 disabled:opacity-40 hover:bg-slate-50"
              >
                ←
              </button>
              <button
                disabled={page + 1 >= totalPages}
                onClick={() => setPage((p) => p + 1)}
                className="px-3 py-1.5 rounded-lg border border-slate-300 disabled:opacity-40 hover:bg-slate-50"
              >
                →
              </button>
            </div>
          </div>
        )}
      </div>

      {openId && (
        <UserDetailDrawer
          userId={openId}
          isSuperadmin={me?.role === 'superadmin'}
          onClose={() => setOpenId(null)}
          onChange={() => {
            // Refresh list when detail mutates the user
            setLoading(true);
            apiGet<UsersResp>(
              `/admin/users?limit=${PAGE_SIZE}&offset=${page * PAGE_SIZE}&search=${encodeURIComponent(debounced)}`,
            )
              .then(setData)
              .catch(() => null)
              .finally(() => setLoading(false));
          }}
        />
      )}

      <BalanceAdjustModal
        open={!!balanceTarget}
        userName={balanceTarget?.full_name || balanceTarget?.username || ''}
        currentBalance={balanceTarget?.balance}
        busy={balanceBusy}
        onCancel={() => setBalanceTarget(null)}
        onSubmit={performBalance}
      />

      <ConfirmDialog
        open={!!blockTarget}
        title={
          blockTarget?.is_blocked
            ? t('admin.users.unblockConfirmTitle')
            : t('admin.users.blockConfirmTitle')
        }
        message={
          blockTarget
            ? t(blockTarget.is_blocked ? 'admin.users.unblockConfirmMsg' : 'admin.users.blockConfirmMsg', {
                name: blockTarget.full_name || blockTarget.username,
              })
            : ''
        }
        confirmLabel={
          blockTarget?.is_blocked ? t('admin.users.unblock') : t('admin.users.block')
        }
        cancelLabel={t('admin.cards.cancel')}
        tone={blockTarget?.is_blocked ? 'default' : 'danger'}
        onCancel={() => setBlockTarget(null)}
        onConfirm={() => blockTarget && performBlock(blockTarget)}
      />
    </div>
  );
}

function RoleBadge({ role }: { role: string }) {
  const map: Record<string, string> = {
    superadmin: 'bg-rose-100 text-rose-700 border-rose-200',
    admin:      'bg-violet-100 text-violet-700 border-violet-200',
    user:       'bg-slate-100 text-slate-600 border-slate-200',
  };
  const cls = map[role] ?? map.user;
  return (
    <span className={`inline-block px-2 py-0.5 rounded-full text-[11px] font-medium border ${cls}`}>
      {role}
    </span>
  );
}

function IconBtn({
  children,
  onClick,
  title,
  tone = 'slate',
}: {
  children: React.ReactNode;
  onClick: () => void;
  title: string;
  tone?: 'slate' | 'rose' | 'emerald';
}) {
  const map = {
    slate:   'text-slate-500 hover:bg-slate-100 hover:text-slate-700',
    rose:    'text-rose-500 hover:bg-rose-50',
    emerald: 'text-emerald-600 hover:bg-emerald-50',
  };
  return (
    <button
      onClick={onClick}
      title={title}
      className={`w-8 h-8 grid place-items-center rounded-lg transition ${map[tone]}`}
    >
      {children}
    </button>
  );
}
