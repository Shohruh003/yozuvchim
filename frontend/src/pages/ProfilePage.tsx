import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

import { apiGet } from '@/lib/api';
import { formatNumber } from '@/lib/utils';
import { StatusBadge } from '@/components/StatusBadge';

interface Me {
  id: string;
  username: string;
  full_name: string;
  balance: number;
  plan: string;
  total_orders: number;
  completed_orders: number;
  total_documents: number;
  total_spent: number;
}
interface OrderRow {
  id: number;
  doc_type: string;
  doc_label: string;
  title: string;
  status: string;
}

export default function ProfilePage() {
  const { t } = useTranslation();
  const [me, setMe] = useState<Me | null>(null);
  const [orders, setOrders] = useState<OrderRow[]>([]);

  useEffect(() => {
    apiGet<Me>('/users/me').then(setMe).catch(() => null);
    apiGet<{ items: OrderRow[] }>('/orders?limit=5')
      .then((r) => setOrders(r.items))
      .catch(() => setOrders([]));
  }, []);

  return (
    <div className="grid md:grid-cols-3 gap-5">
      <aside className="md:col-span-1 bg-white rounded-2xl shadow-sm border border-slate-200 p-6">
        <div className="w-20 h-20 rounded-full bg-brand-500 text-white grid place-items-center text-2xl font-bold mx-auto">
          {(me?.full_name || 'U').slice(0, 1).toUpperCase()}
        </div>
        <h2 className="text-center text-xl font-bold mt-3">{me?.full_name || '—'}</h2>
        <p className="text-center text-slate-500 text-sm">
          {me?.username ? '@' + me.username : ''}
        </p>
        <span className="mt-3 mx-auto block w-fit px-3 py-1 rounded-full text-xs font-semibold bg-slate-100 text-slate-700">
          {me?.plan ?? '—'}
        </span>

        <div className="mt-6 p-4 rounded-xl bg-gradient-to-br from-brand-500 to-brand-700 text-white text-center">
          <div className="text-xs opacity-80">{t('profile.balance')}</div>
          <div className="text-3xl font-extrabold mt-1">{formatNumber(me?.balance)} so'm</div>
          <Link
            to="/payments"
            className="mt-3 inline-block px-4 py-2 bg-white/20 hover:bg-white/30 rounded-lg text-sm"
          >
            {t('profile.topUp')}
          </Link>
        </div>
      </aside>

      <section className="md:col-span-2 grid grid-cols-2 gap-4">
        <Stat label={t('profile.stats.orders')} value={me?.total_orders} />
        <Stat label={t('profile.stats.completed')} value={me?.completed_orders} />
        <Stat label={t('profile.stats.documents')} value={me?.total_documents} />
        <Stat label={t('profile.stats.spent')} value={me?.total_spent} suffix=" so'm" />

        <div className="col-span-2 bg-white rounded-2xl shadow-sm border border-slate-200 p-5">
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-semibold">{t('profile.recentOrders')}</h3>
            <Link to="/orders" className="text-brand-600 text-sm">
              {t('profile.viewAll')} →
            </Link>
          </div>
          {orders.length === 0 ? (
            <div className="text-slate-400 text-sm">{t('profile.noOrders')}</div>
          ) : (
            <div className="space-y-2">
              {orders.map((o) => (
                <Link
                  key={o.id}
                  to={`/orders/${o.id}`}
                  className="flex items-center justify-between gap-3 p-3 rounded-xl hover:bg-slate-50 border border-slate-100"
                >
                  <div className="min-w-0 flex-1">
                    <div className="font-medium text-sm">
                      {t(`docTypes.${o.doc_type}`, { defaultValue: o.doc_label })}
                    </div>
                    <div className="text-xs text-slate-500 truncate">{o.title}</div>
                  </div>
                  <div className="shrink-0">
                    <StatusBadge status={o.status} />
                  </div>
                </Link>
              ))}
            </div>
          )}
        </div>
      </section>

      <Link
        to="/orders/new"
        className="md:col-span-3 mt-2 flex items-center justify-center gap-2 w-full px-5 py-3 rounded-xl bg-brand-500 text-white font-semibold hover:bg-brand-600 shadow-sm"
      >
        {t('profile.createNew')}
      </Link>
    </div>
  );
}

function Stat({ label, value, suffix = '' }: { label: string; value?: number; suffix?: string }) {
  return (
    <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-5">
      <div className="text-slate-500 text-sm">{label}</div>
      <div className="text-3xl font-bold mt-2">
        {value === undefined ? '—' : formatNumber(value)}
        {suffix}
      </div>
    </div>
  );
}
