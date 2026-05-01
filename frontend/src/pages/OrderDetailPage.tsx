import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';

import { apiGet } from '@/lib/api';
import { formatNumber } from '@/lib/utils';
import { StatusBadge } from '@/components/StatusBadge';

interface OrderDetail {
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
  meta?: Record<string, unknown>;
  result_text?: string;
  error_log?: string;
}

export default function OrderDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [order, setOrder] = useState<OrderDetail | null>(null);

  useEffect(() => {
    if (!id) return;
    let cancelled = false;
    let timer: number | null = null;

    async function load() {
      try {
        const o = await apiGet<OrderDetail>(`/orders/${id}`);
        if (cancelled) return;
        setOrder(o);
        if (o.status === 'queued' || o.status === 'processing') {
          timer = window.setTimeout(load, 5000);
        }
      } catch {
        /* noop */
      }
    }
    load();
    return () => {
      cancelled = true;
      if (timer) window.clearTimeout(timer);
    };
  }, [id]);

  if (!order) return <div className="text-slate-400 text-sm">Yuklanmoqda...</div>;

  const pct = Math.round((order.current_step / Math.max(order.total_steps, 1)) * 100);

  return (
    <>
      <Link to="/orders" className="text-brand-600 text-sm">
        ← Buyurtmalar
      </Link>

      <div className="bg-white rounded-2xl border border-slate-200 p-6 mt-3">
        <div className="flex items-start justify-between gap-4 mb-3">
          <div>
            <div className="text-slate-500 text-sm">{order.doc_label}</div>
            <h2 className="text-xl font-bold mt-1">{order.title}</h2>
          </div>
          <StatusBadge status={order.status} />
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-4">
          <Field label="Til" value={order.language.toUpperCase()} />
          <Field label="Hajm" value={order.length} />
          <Field label="Narxi" value={`${formatNumber(order.price)} so'm`} />
          <Field label="Sana" value={new Date(order.created_at).toLocaleDateString('uz-UZ')} />
        </div>
        {order.error_log && (
          <div className="mt-4 bg-rose-50 border border-rose-200 rounded-xl p-3 text-sm text-rose-700 whitespace-pre-wrap">
            {order.error_log}
          </div>
        )}
      </div>

      {(order.status === 'queued' || order.status === 'processing') && (
        <div className="bg-white rounded-2xl border border-slate-200 p-6 mt-4">
          <div className="flex items-center justify-between mb-2">
            <h3 className="font-semibold">Tayyorlanmoqda</h3>
            <span className="text-sm text-slate-500">{pct}%</span>
          </div>
          <div className="h-3 bg-slate-100 rounded-full overflow-hidden">
            <div className="h-full bg-brand-500 transition-all" style={{ width: `${pct}%` }} />
          </div>
          <p className="text-xs text-slate-500 mt-2">
            Bu sahifa har 5 soniyada o'zi yangilanadi.
          </p>
        </div>
      )}

      {order.has_file && (
        <div className="bg-white rounded-2xl border border-slate-200 p-6 mt-4">
          <h3 className="font-semibold mb-3">Natija</h3>
          <a
            href={`/api/orders/${order.id}/download`}
            className="inline-block px-5 py-3 rounded-xl bg-emerald-500 text-white font-semibold hover:bg-emerald-600"
          >
            📥 Yuklab olish
          </a>
        </div>
      )}
    </>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-slate-50 rounded-xl p-3">
      <div className="text-xs text-slate-500">{label}</div>
      <div className="font-semibold mt-0.5">{value}</div>
    </div>
  );
}
