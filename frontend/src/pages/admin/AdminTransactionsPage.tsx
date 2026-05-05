import { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts';
import { Calendar, Wallet } from 'lucide-react';

import { apiGet } from '@/lib/api';
import { formatNumber } from '@/lib/utils';

interface Tx {
  id: number;
  user_id: string;
  username: string;
  full_name: string;
  invoice_id: string;
  amount: number;
  status: string;
  created_at: string;
}

interface TxResp {
  total: number;
  sum_approved: number;
  count_approved: number;
  items: Tx[];
}

interface Point {
  ts: string;
  value: number;
}

const STATUSES = ['all', 'approved', 'pending', 'rejected'] as const;
type StatusFilter = (typeof STATUSES)[number];

const PAGE_SIZE = 20;

// Local YYYY-MM-DDTHH:mm value for <input type="datetime-local"> in user's timezone
function toLocalInput(d: Date): string {
  const pad = (n: number) => String(n).padStart(2, '0');
  return (
    `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}` +
    `T${pad(d.getHours())}:${pad(d.getMinutes())}`
  );
}

export default function AdminTransactionsPage() {
  const { t, i18n } = useTranslation();

  // Default range: last 7 days, full hour granularity
  const [from, setFrom] = useState<string>(() => {
    const d = new Date(Date.now() - 7 * 86_400_000);
    d.setMinutes(0, 0, 0);
    return toLocalInput(d);
  });
  const [to, setTo] = useState<string>(() => toLocalInput(new Date()));
  const [status, setStatus] = useState<StatusFilter>('all');
  const [page, setPage] = useState(0);

  const [data, setData] = useState<TxResp | null>(null);
  const [series, setSeries] = useState<Point[]>([]);
  const [loading, setLoading] = useState(false);

  const params = useMemo(() => {
    const fromIso = new Date(from).toISOString();
    const toIso = new Date(to).toISOString();
    return { fromIso, toIso };
  }, [from, to]);

  // Decide bucket: if range > 5 days -> day, else hour
  const bucket = useMemo<'hour' | 'day'>(() => {
    const diffH = (new Date(to).getTime() - new Date(from).getTime()) / 3_600_000;
    return diffH > 24 * 5 ? 'day' : 'hour';
  }, [from, to]);

  useEffect(() => {
    setPage(0);
  }, [from, to, status]);

  useEffect(() => {
    setLoading(true);
    const q = new URLSearchParams({
      from: params.fromIso,
      to: params.toIso,
      status,
      limit: String(PAGE_SIZE),
      offset: String(page * PAGE_SIZE),
    }).toString();
    Promise.all([
      apiGet<TxResp>(`/admin/transactions?${q}`),
      apiGet<Point[]>(
        `/admin/revenue/timeseries?from=${encodeURIComponent(params.fromIso)}&to=${encodeURIComponent(params.toIso)}&bucket=${bucket}`,
      ),
    ])
      .then(([t, s]) => { setData(t); setSeries(s); })
      .catch(() => null)
      .finally(() => setLoading(false));
  }, [params, status, page, bucket]);

  const totalPages = useMemo(
    () => (data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1),
    [data],
  );

  function setQuickRange(days: number) {
    const t = new Date();
    const f = new Date(Date.now() - days * 86_400_000);
    if (days >= 1) f.setHours(0, 0, 0, 0);
    setFrom(toLocalInput(f));
    setTo(toLocalInput(t));
  }

  const fmtTick = (s: string) => {
    const d = new Date(s);
    if (bucket === 'hour') {
      return d.toLocaleTimeString(i18n.language === 'ru' ? 'ru-RU' : 'uz-UZ', {
        hour: '2-digit', minute: '2-digit',
      });
    }
    return d.toLocaleDateString(i18n.language === 'ru' ? 'ru-RU' : 'uz-UZ', {
      month: 'short', day: 'numeric',
    });
  };
  const fmtRow = (s: string) =>
    new Date(s).toLocaleString(i18n.language === 'ru' ? 'ru-RU' : 'uz-UZ', {
      day: '2-digit', month: 'short', year: 'numeric',
      hour: '2-digit', minute: '2-digit',
    });

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl sm:text-2xl font-bold text-slate-900">
          {t('admin.tx.title')}
        </h1>
        <p className="text-sm text-slate-500 mt-0.5">{t('admin.tx.subtitle')}</p>
      </div>

      {/* Filters */}
      <div className="bg-white rounded-2xl border border-slate-200 p-4 space-y-3">
        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3">
          <Field label={t('admin.tx.from')}>
            <DateTimeInput value={from} onChange={setFrom} />
          </Field>
          <Field label={t('admin.tx.to')}>
            <DateTimeInput value={to} onChange={setTo} />
          </Field>
          <Field label={t('admin.tx.status')}>
            <select
              value={status}
              onChange={(e) => setStatus(e.target.value as StatusFilter)}
              className="w-full border border-slate-300 rounded-xl px-3 py-2 text-sm bg-white"
            >
              {STATUSES.map((s) => (
                <option key={s} value={s}>{t(`admin.tx.statusOpt.${s}`)}</option>
              ))}
            </select>
          </Field>
          <Field label={t('admin.tx.quick')}>
            <div className="flex gap-1.5 flex-wrap">
              {[1, 7, 30, 90].map((d) => (
                <button
                  key={d}
                  onClick={() => setQuickRange(d)}
                  className="px-2.5 py-1.5 rounded-lg text-xs border border-slate-300 hover:bg-slate-50"
                >
                  {d}d
                </button>
              ))}
            </div>
          </Field>
        </div>
      </div>

      {/* Summary */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <SumCard
          label={t('admin.tx.totalIncome')}
          value={`${formatNumber(data?.sum_approved ?? 0)} so'm`}
          icon={<Wallet size={16} />}
        />
        <SumCard
          label={t('admin.tx.approvedCount')}
          value={formatNumber(data?.count_approved ?? 0)}
          icon={<Calendar size={16} />}
        />
        <SumCard
          label={t('admin.tx.totalCount')}
          value={formatNumber(data?.total ?? 0)}
          icon={<Calendar size={16} />}
        />
      </div>

      {/* Chart */}
      <div className="bg-white rounded-2xl border border-slate-200 p-4 sm:p-5">
        <div className="flex items-center justify-between mb-3">
          <h3 className="font-semibold text-slate-900 text-sm sm:text-base">
            {t('admin.tx.chart', { bucket: t(`admin.tx.bucket.${bucket}`) })}
          </h3>
        </div>
        <ResponsiveContainer width="100%" height={260}>
          <AreaChart data={series}>
            <defs>
              <linearGradient id="txGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#6366f1" stopOpacity={0.45} />
                <stop offset="100%" stopColor="#6366f1" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
            <XAxis dataKey="ts" tickFormatter={fmtTick} tick={{ fontSize: 11, fill: '#94a3b8' }} />
            <YAxis tickFormatter={(v) => formatNumber(v)} tick={{ fontSize: 11, fill: '#94a3b8' }} />
            <Tooltip
              formatter={(v) => [`${formatNumber(Number(v))} so'm`, t('admin.tx.income')]}
              labelFormatter={(d) => fmtRow(String(d))}
              contentStyle={{
                borderRadius: 12, border: '1px solid #e2e8f0', fontSize: 12,
              }}
            />
            <Area type="monotone" dataKey="value" stroke="#6366f1" strokeWidth={2} fill="url(#txGrad)" />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      {/* Table */}
      <div className="bg-white rounded-2xl border border-slate-200 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-slate-500 text-xs uppercase">
              <tr>
                <th className="text-left px-4 py-3 font-medium">{t('admin.tx.col.user')}</th>
                <th className="text-left px-4 py-3 font-medium">{t('admin.tx.col.invoice')}</th>
                <th className="text-right px-4 py-3 font-medium">{t('admin.tx.col.amount')}</th>
                <th className="text-left px-4 py-3 font-medium">{t('admin.tx.col.status')}</th>
                <th className="text-left px-4 py-3 font-medium">{t('admin.tx.col.date')}</th>
              </tr>
            </thead>
            <tbody>
              {loading && !data && (
                <tr><td colSpan={5} className="px-4 py-8 text-center text-slate-400">{t('common.loading')}</td></tr>
              )}
              {data?.items.map((p) => (
                <tr key={p.id} className="border-t border-slate-100 hover:bg-slate-50/50">
                  <td className="px-4 py-3">
                    <div className="font-medium text-slate-900 truncate max-w-[200px]">
                      {p.full_name || p.username || `#${p.user_id}`}
                    </div>
                    <div className="text-xs text-slate-500">
                      {p.username ? `@${p.username}` : `#${p.user_id}`}
                    </div>
                  </td>
                  <td className="px-4 py-3 text-xs text-slate-500 font-mono">{p.invoice_id}</td>
                  <td className="px-4 py-3 text-right tabular-nums font-medium text-slate-900">
                    {formatNumber(p.amount)}
                  </td>
                  <td className="px-4 py-3">
                    <StatusPill status={p.status} />
                  </td>
                  <td className="px-4 py-3 text-slate-600">{fmtRow(p.created_at)}</td>
                </tr>
              ))}
              {data && data.items.length === 0 && (
                <tr><td colSpan={5} className="px-4 py-8 text-center text-slate-400">{t('admin.tx.empty')}</td></tr>
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
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="block text-[11px] uppercase tracking-wide text-slate-500 font-medium mb-1">
        {label}
      </label>
      {children}
    </div>
  );
}

function DateTimeInput({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  return (
    <input
      type="datetime-local"
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="w-full border border-slate-300 rounded-xl px-3 py-2 text-sm bg-white"
    />
  );
}

function SumCard({
  label,
  value,
  icon,
}: {
  label: string;
  value: string;
  icon: React.ReactNode;
}) {
  return (
    <div className="bg-white rounded-2xl border border-slate-200 p-4 flex items-center gap-3">
      <div className="w-10 h-10 grid place-items-center rounded-xl bg-brand-50 text-brand-600">
        {icon}
      </div>
      <div className="min-w-0">
        <div className="text-xs text-slate-500">{label}</div>
        <div className="text-lg font-bold text-slate-900 truncate">{value}</div>
      </div>
    </div>
  );
}

function StatusPill({ status }: { status: string }) {
  const map: Record<string, string> = {
    approved: 'bg-emerald-100 text-emerald-700 border-emerald-200',
    pending:  'bg-amber-100 text-amber-700 border-amber-200',
    rejected: 'bg-rose-100 text-rose-700 border-rose-200',
  };
  return (
    <span className={`text-[11px] px-2 py-0.5 rounded-full font-medium border ${map[status] ?? map.pending}`}>
      {status}
    </span>
  );
}
