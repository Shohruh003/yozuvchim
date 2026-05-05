import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { ChevronDown, ShieldCheck, Sparkles } from 'lucide-react';

import { apiGet } from '@/lib/api';
import { formatNumber } from '@/lib/utils';
import { StatusBadge } from '@/components/StatusBadge';

interface Admin {
  id: string;
  username: string;
  full_name: string;
  role: string;
  created_at: string;
  last_active: string;
  total_orders: number;
  by_type: Record<string, number>;
}

interface OrderItem {
  id: number;
  doc_type: string;
  title: string;
  status: string;
  length: string;
  price: number;
  is_free: boolean;
  created_at: string;
}

export default function AdminAdminsPage() {
  const { t, i18n } = useTranslation();
  const [admins, setAdmins] = useState<Admin[] | null>(null);
  const [openId, setOpenId] = useState<string | null>(null);
  const [activity, setActivity] = useState<OrderItem[] | null>(null);

  useEffect(() => {
    apiGet<Admin[]>('/admin/admins').then(setAdmins).catch(() => setAdmins([]));
  }, []);

  function toggle(id: string) {
    if (openId === id) {
      setOpenId(null);
      setActivity(null);
      return;
    }
    setOpenId(id);
    setActivity(null);
    apiGet<OrderItem[]>(`/admin/admins/${id}/activity?limit=200`)
      .then(setActivity)
      .catch(() => setActivity([]));
  }

  const fmtDate = (s: string) =>
    new Date(s).toLocaleString(i18n.language === 'ru' ? 'ru-RU' : 'uz-UZ', {
      day: '2-digit', month: 'short', year: 'numeric',
      hour: '2-digit', minute: '2-digit',
    });

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl sm:text-2xl font-bold text-slate-900">
          {t('admin.admins.title')}
        </h1>
        <p className="text-sm text-slate-500 mt-0.5">{t('admin.admins.subtitle')}</p>
      </div>

      {!admins ? (
        <div className="text-slate-400 text-sm">{t('common.loading')}</div>
      ) : admins.length === 0 ? (
        <div className="bg-white rounded-2xl border border-slate-200 p-10 text-center text-slate-400">
          {t('admin.admins.empty')}
        </div>
      ) : (
        <div className="space-y-3">
          {admins.map((a) => {
            const isOpen = openId === a.id;
            const types = Object.entries(a.by_type).sort((x, y) => y[1] - x[1]);
            return (
              <div
                key={a.id}
                className="bg-white rounded-2xl border border-slate-200 overflow-hidden"
              >
                <button
                  onClick={() => toggle(a.id)}
                  className="w-full text-left px-4 sm:px-5 py-4 flex items-start sm:items-center justify-between gap-3 hover:bg-slate-50/50 transition"
                >
                  <div className="flex items-start gap-3 min-w-0 flex-1">
                    <div
                      className={
                        'shrink-0 w-10 h-10 grid place-items-center rounded-xl text-white ' +
                        (a.role === 'superadmin'
                          ? 'bg-gradient-to-br from-rose-500 to-rose-700'
                          : 'bg-gradient-to-br from-violet-500 to-purple-700')
                      }
                    >
                      {a.role === 'superadmin' ? <Sparkles size={18} /> : <ShieldCheck size={18} />}
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="font-semibold text-slate-900 truncate">
                          {a.full_name || a.username || `#${a.id}`}
                        </span>
                        <span
                          className={
                            'text-[10px] px-2 py-0.5 rounded-full font-medium border ' +
                            (a.role === 'superadmin'
                              ? 'bg-rose-100 text-rose-700 border-rose-200'
                              : 'bg-violet-100 text-violet-700 border-violet-200')
                          }
                        >
                          {a.role}
                        </span>
                      </div>
                      <div className="text-xs text-slate-500 mt-0.5">
                        {a.username ? `@${a.username} · ` : ''}#{a.id}
                      </div>
                      {types.length > 0 && (
                        <div className="flex gap-1.5 flex-wrap mt-2">
                          {types.map(([type, count]) => (
                            <span
                              key={type}
                              className="text-[11px] px-2 py-0.5 rounded-md bg-slate-100 text-slate-700"
                            >
                              {t(`docTypes.${type}`, type)}:{' '}
                              <span className="font-semibold tabular-nums">{count}</span>
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-3 shrink-0">
                    <div className="text-right">
                      <div className="text-2xl font-bold text-slate-900 tabular-nums">
                        {formatNumber(a.total_orders)}
                      </div>
                      <div className="text-[10px] uppercase tracking-wide text-slate-400">
                        {t('admin.admins.orders')}
                      </div>
                    </div>
                    <ChevronDown
                      size={18}
                      className={`text-slate-400 transition-transform ${isOpen ? 'rotate-180' : ''}`}
                    />
                  </div>
                </button>

                {isOpen && (
                  <div className="border-t border-slate-100 px-4 sm:px-5 py-4 bg-slate-50/40">
                    <h4 className="text-xs uppercase tracking-wide text-slate-500 font-semibold mb-3">
                      {t('admin.admins.recentOrders')}
                    </h4>
                    {!activity ? (
                      <div className="text-sm text-slate-400 py-4">{t('common.loading')}</div>
                    ) : activity.length === 0 ? (
                      <div className="text-sm text-slate-400 py-4">{t('admin.admins.noActivity')}</div>
                    ) : (
                      <ul className="space-y-2">
                        {activity.map((o) => (
                          <li
                            key={o.id}
                            className="flex items-start justify-between gap-3 p-3 rounded-xl bg-white border border-slate-200"
                          >
                            <div className="min-w-0 flex-1">
                              <div className="flex items-center gap-2 mb-0.5 flex-wrap">
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
                            <div className="shrink-0">
                              <StatusBadge status={o.status} />
                            </div>
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
