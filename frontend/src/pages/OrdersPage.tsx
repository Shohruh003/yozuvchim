import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

import { apiGet } from '@/lib/api';
import { formatDate, formatNumber } from '@/lib/utils';
import { StatusBadge } from '@/components/StatusBadge';

interface Order {
  id: number;
  doc_type: string;
  doc_label: string;
  title: string;
  status: string;
  language: string;
  length: string;
  price: number;
  created_at: string;
  current_step: number;
  total_steps: number;
  has_file: boolean;
}

interface OrdersResp {
  total: number;
  items: Order[];
}

const PAGE_SIZE = 20;

export default function OrdersPage() {
  const { t } = useTranslation();
  const [data, setData] = useState<OrdersResp | null>(null);
  const [page, setPage] = useState(0);

  useEffect(() => {
    apiGet<OrdersResp>(`/orders?limit=${PAGE_SIZE}&offset=${page * PAGE_SIZE}`)
      .then(setData)
      .catch(() => setData({ total: 0, items: [] }));
  }, [page]);

  const totalPages = useMemo(
    () => (data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1),
    [data],
  );

  return (
    <>
      <h1 className="text-xl sm:text-2xl font-bold mb-4">{t('orders.title')}</h1>

      <Link
        to="/orders/new"
        className="flex items-center justify-center gap-2 mb-5 px-5 py-3 rounded-xl bg-brand-500 text-white font-semibold hover:bg-brand-600 shadow-sm"
      >
        {t('orders.newOrderBtn')}
      </Link>

      {data === null ? (
        <div className="text-slate-400 text-sm">{t('orders.loading')}</div>
      ) : data.items.length === 0 ? (
        <div className="bg-white rounded-2xl border border-slate-200 p-10 text-center">
          <p className="text-slate-600 mb-4">{t('orders.empty')}</p>
        </div>
      ) : (
        <>
          <div className="space-y-3">
            {data.items.map((o) => (
              <Link
                key={o.id}
                to={`/orders/${o.id}`}
                className="block bg-white rounded-2xl border border-slate-200 hover:border-brand-300 hover:shadow-md transition p-5"
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="font-semibold">{o.doc_label}</span>
                      <StatusBadge status={o.status} />
                    </div>
                    <div className="text-slate-700 truncate">{o.title}</div>
                    <div className="text-xs text-slate-400 mt-1">
                      {formatDate(o.created_at)} · {o.length} {t('orders.pages')} · {o.language.toUpperCase()}
                    </div>
                  </div>
                  <div className="text-right shrink-0">
                    <div className="font-bold text-brand-700">{formatNumber(o.price)} so'm</div>
                    {o.has_file && (
                      <div className="text-xs text-emerald-600 mt-1">{t('orders.downloadable')}</div>
                    )}
                  </div>
                </div>
                {o.status === 'processing' && (
                  <div className="mt-3 h-2 bg-slate-100 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-brand-500 transition-all"
                      style={{ width: `${(o.current_step / Math.max(o.total_steps, 1)) * 100}%` }}
                    />
                  </div>
                )}
              </Link>
            ))}
          </div>

          {data.total > PAGE_SIZE && (
            <div className="flex items-center justify-between mt-4 text-sm">
              <div className="text-slate-500">
                {t('admin.users.pageOf', { current: page + 1, total: totalPages })}
              </div>
              <div className="flex gap-2">
                <button
                  disabled={page === 0}
                  onClick={() => setPage((p) => Math.max(0, p - 1))}
                  className="px-3 py-1.5 rounded-lg border border-slate-300 disabled:opacity-40 hover:bg-slate-50 bg-white"
                >
                  ←
                </button>
                <button
                  disabled={page + 1 >= totalPages}
                  onClick={() => setPage((p) => p + 1)}
                  className="px-3 py-1.5 rounded-lg border border-slate-300 disabled:opacity-40 hover:bg-slate-50 bg-white"
                >
                  →
                </button>
              </div>
            </div>
          )}
        </>
      )}
    </>
  );
}
