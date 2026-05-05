import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { TrendingUp, Users, ShoppingBag, Wallet, Ban, Sparkles } from 'lucide-react';

import { apiGet } from '@/lib/api';
import { formatNumber } from '@/lib/utils';

interface Stats {
  users: { total: number; blocked: number; new_this_week: number };
  orders: { total: number; today: number };
  revenue: { today: number; week: number; month: number; total: number };
  orders_by_type: Array<{ doc_type: string; count: number }>;
  orders_by_status: Array<{ status: string; count: number }>;
  revenue_series: Array<{ date: string; value: number }>;
  users_growth: Array<{ date: string; value: number }>;
}

const STATUS_COLORS: Record<string, string> = {
  done:       '#10b981',
  processing: '#f59e0b',
  queued:     '#6366f1',
  error:      '#ef4444',
  cancelled:  '#94a3b8',
};

const TYPE_COLORS = [
  '#6366f1', '#8b5cf6', '#ec4899', '#f43f5e',
  '#f97316', '#eab308', '#10b981', '#06b6d4',
];

export default function AdminDashboardPage() {
  const { t, i18n } = useTranslation();
  const [s, setS] = useState<Stats | null>(null);

  useEffect(() => {
    apiGet<Stats>('/admin/stats').then(setS).catch(() => null);
    const id = window.setInterval(() => {
      apiGet<Stats>('/admin/stats').then(setS).catch(() => null);
    }, 30_000);
    return () => window.clearInterval(id);
  }, []);

  if (!s) {
    return <div className="text-slate-400 text-sm">Yuklanmoqda...</div>;
  }

  const fmtDate = (d: string) =>
    new Date(d).toLocaleDateString(i18n.language === 'ru' ? 'ru-RU' : 'uz-UZ', {
      month: 'short',
      day: 'numeric',
    });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl sm:text-2xl font-bold text-slate-900">
          {t('admin.dashboard.title')}
        </h1>
        <p className="text-sm text-slate-500 mt-0.5">
          {t('admin.dashboard.subtitle')}
        </p>
      </div>

      {/* Top stat cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
        <StatCard
          label={t('admin.stat.totalRevenue')}
          value={`${formatNumber(s.revenue.total)} so'm`}
          icon={<Wallet size={18} />}
          gradient="from-emerald-500 to-teal-600"
          sub={`${formatNumber(s.revenue.month)} ${t('admin.thisMonth')}`}
        />
        <StatCard
          label={t('admin.stat.users')}
          value={formatNumber(s.users.total)}
          icon={<Users size={18} />}
          gradient="from-indigo-500 to-blue-600"
          sub={`+${s.users.new_this_week} ${t('admin.thisWeek')}`}
        />
        <StatCard
          label={t('admin.stat.orders')}
          value={formatNumber(s.orders.total)}
          icon={<ShoppingBag size={18} />}
          gradient="from-fuchsia-500 to-purple-600"
          sub={`${s.orders.today} ${t('admin.today')}`}
        />
        <StatCard
          label={t('admin.stat.todayRevenue')}
          value={`${formatNumber(s.revenue.today)} so'm`}
          icon={<TrendingUp size={18} />}
          gradient="from-amber-500 to-orange-600"
          sub={`${formatNumber(s.revenue.week)} ${t('admin.thisWeek')}`}
        />
      </div>

      {/* Mini metrics row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <MiniRow
          icon={<Sparkles size={16} className="text-emerald-600" />}
          label={t('admin.activeUsers')}
          value={`${formatNumber(s.users.total - s.users.blocked)} / ${formatNumber(s.users.total)}`}
          tone="emerald"
        />
        <MiniRow
          icon={<Ban size={16} className="text-rose-600" />}
          label={t('admin.blockedUsers')}
          value={`${formatNumber(s.users.blocked)}`}
          tone="rose"
        />
      </div>

      {/* Charts row 1: revenue area + user growth line */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <ChartCard title={t('admin.chart.revenue30d')}>
          <ResponsiveContainer width="100%" height={260}>
            <AreaChart data={s.revenue_series}>
              <defs>
                <linearGradient id="revGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#10b981" stopOpacity={0.5} />
                  <stop offset="100%" stopColor="#10b981" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis dataKey="date" tickFormatter={fmtDate} tick={{ fontSize: 11, fill: '#94a3b8' }} />
              <YAxis tick={{ fontSize: 11, fill: '#94a3b8' }} tickFormatter={(v) => formatNumber(v)} />
              <Tooltip
                content={<ChartTooltip suffix=" so'm" />}
                labelFormatter={(d) => fmtDate(String(d))}
              />
              <Area
                type="monotone"
                dataKey="value"
                stroke="#10b981"
                strokeWidth={2}
                fill="url(#revGrad)"
              />
            </AreaChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title={t('admin.chart.userGrowth30d')}>
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={s.users_growth}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis dataKey="date" tickFormatter={fmtDate} tick={{ fontSize: 11, fill: '#94a3b8' }} />
              <YAxis tick={{ fontSize: 11, fill: '#94a3b8' }} allowDecimals={false} />
              <Tooltip content={<ChartTooltip />} labelFormatter={(d) => fmtDate(String(d))} />
              <Line
                type="monotone"
                dataKey="value"
                stroke="#6366f1"
                strokeWidth={2}
                dot={{ r: 3, fill: '#6366f1' }}
                activeDot={{ r: 5 }}
              />
            </LineChart>
          </ResponsiveContainer>
        </ChartCard>
      </div>

      {/* Charts row 2: bar + pie */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <ChartCard title={t('admin.chart.ordersByType')}>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={s.orders_by_type} layout="vertical" margin={{ left: 12 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" horizontal={false} />
              <XAxis type="number" tick={{ fontSize: 11, fill: '#94a3b8' }} allowDecimals={false} />
              <YAxis
                type="category"
                dataKey="doc_type"
                tick={{ fontSize: 12, fill: '#475569' }}
                tickFormatter={(k) => t(`docTypes.${k}`)}
                width={110}
              />
              <Tooltip content={<ChartTooltip />} labelFormatter={(k) => t(`docTypes.${k}`)} />
              <Bar dataKey="count" radius={[0, 8, 8, 0]}>
                {s.orders_by_type.map((_, i) => (
                  <Cell key={i} fill={TYPE_COLORS[i % TYPE_COLORS.length]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title={t('admin.chart.ordersByStatus')}>
          <ResponsiveContainer width="100%" height={300}>
            <PieChart>
              <Pie
                data={s.orders_by_status}
                dataKey="count"
                nameKey="status"
                cx="50%"
                cy="50%"
                innerRadius={55}
                outerRadius={100}
                paddingAngle={2}
              >
                {s.orders_by_status.map((row, i) => (
                  <Cell key={i} fill={STATUS_COLORS[row.status] || '#64748b'} />
                ))}
              </Pie>
              <Tooltip content={<ChartTooltip />} formatter={(v) => formatNumber(Number(v))} />
              <Legend
                formatter={(value) => (
                  <span className="text-xs text-slate-600">
                    {String(t(`status.${value}`, { defaultValue: value }))}
                  </span>
                )}
              />
            </PieChart>
          </ResponsiveContainer>
        </ChartCard>
      </div>
    </div>
  );
}

function StatCard({
  label,
  value,
  icon,
  gradient,
  sub,
}: {
  label: string;
  value: string;
  icon: React.ReactNode;
  gradient: string;
  sub?: string;
}) {
  return (
    <div className="relative bg-white rounded-2xl border border-slate-200 p-4 overflow-hidden">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="text-xs text-slate-500 font-medium truncate">{label}</div>
          <div className="text-lg sm:text-2xl font-bold text-slate-900 mt-1 truncate">{value}</div>
          {sub && <div className="text-[11px] text-slate-400 mt-1 truncate">{sub}</div>}
        </div>
        <div
          className={`shrink-0 w-9 h-9 grid place-items-center rounded-xl bg-gradient-to-br ${gradient} text-white shadow-sm`}
        >
          {icon}
        </div>
      </div>
    </div>
  );
}

function MiniRow({
  icon,
  label,
  value,
  tone,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  tone: 'emerald' | 'rose';
}) {
  const toneCls =
    tone === 'emerald'
      ? 'bg-emerald-50 border-emerald-200'
      : 'bg-rose-50 border-rose-200';
  return (
    <div className={`flex items-center justify-between rounded-xl border ${toneCls} px-4 py-3`}>
      <div className="flex items-center gap-2 text-sm text-slate-700">
        {icon}
        <span>{label}</span>
      </div>
      <div className="font-semibold text-slate-900">{value}</div>
    </div>
  );
}

function ChartCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="bg-white rounded-2xl border border-slate-200 p-4 sm:p-5">
      <h3 className="font-semibold text-slate-900 mb-4 text-sm sm:text-base">{title}</h3>
      {children}
    </div>
  );
}

function ChartTooltip({ active, payload, label, suffix = '' }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-white border border-slate-200 shadow-lg rounded-xl px-3 py-2 text-xs">
      {label && <div className="text-slate-500 mb-1">{label}</div>}
      {payload.map((p: any, i: number) => (
        <div key={i} className="flex items-center gap-2">
          <span
            className="w-2 h-2 rounded-full"
            style={{ background: p.color || p.fill || '#6366f1' }}
          />
          <span className="font-medium text-slate-900">
            {formatNumber(Number(p.value))}
            {suffix}
          </span>
        </div>
      ))}
    </div>
  );
}
