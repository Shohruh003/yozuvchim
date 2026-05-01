import { useEffect, useState } from 'react';
import { apiGet } from '@/lib/api';
import { formatNumber } from '@/lib/utils';

interface PaymentInfo {
  card_number: string;
  card_holder: string;
  currency: string;
}

interface PaymentRow {
  id: number;
  amount: number;
  status: string;
  created_at: string;
}

const STATUS_LABEL: Record<string, string> = {
  approved: 'Tasdiqlangan',
  pending: 'Kutilmoqda',
  rejected: 'Rad etilgan',
};
const STATUS_COLOR: Record<string, string> = {
  approved: 'text-emerald-600',
  pending: 'text-amber-600',
  rejected: 'text-rose-600',
};

export default function PaymentsPage() {
  const [info, setInfo] = useState<PaymentInfo | null>(null);
  const [history, setHistory] = useState<PaymentRow[] | null>(null);

  useEffect(() => {
    apiGet<PaymentInfo>('/payments/info').then(setInfo).catch(() => null);
    apiGet<PaymentRow[]>('/payments/history').then(setHistory).catch(() => setHistory([]));
  }, []);

  return (
    <>
      <h1 className="text-xl sm:text-2xl font-bold mb-5">Hisobni to'ldirish</h1>

      <div className="grid md:grid-cols-2 gap-5">
        <section className="bg-white rounded-2xl border border-slate-200 p-6">
          <h3 className="font-semibold mb-4">To'lov ma'lumotlari</h3>
          <div className="space-y-3">
            <div>
              <div className="text-xs text-slate-500">Karta raqami</div>
              <div className="text-2xl font-mono font-bold mt-1">
                {info?.card_number || '—'}
              </div>
            </div>
            <div>
              <div className="text-xs text-slate-500">Karta egasi</div>
              <div className="font-semibold mt-1">{info?.card_holder || '—'}</div>
            </div>
          </div>
          <div className="mt-6 p-4 bg-amber-50 rounded-xl text-sm text-amber-800 border border-amber-200">
            To'lovdan keyin, screenshot ni botga yuboring. Admin tasdiqlagandan keyin
            balansga qo'shiladi.
          </div>
        </section>

        <section className="bg-white rounded-2xl border border-slate-200 p-6">
          <h3 className="font-semibold mb-4">To'lovlar tarixi</h3>
          {history === null ? (
            <div className="text-slate-400 text-sm">Yuklanmoqda...</div>
          ) : history.length === 0 ? (
            <div className="text-slate-400 text-sm">Tarix bo'sh</div>
          ) : (
            <div className="space-y-2">
              {history.map((p) => (
                <div
                  key={p.id}
                  className="flex items-center justify-between p-3 rounded-xl border border-slate-100"
                >
                  <div>
                    <div className="font-semibold">{formatNumber(p.amount)} so'm</div>
                    <div className="text-xs text-slate-500">
                      {new Date(p.created_at).toLocaleString('uz-UZ')}
                    </div>
                  </div>
                  <span className={`text-sm font-medium ${STATUS_COLOR[p.status] ?? ''}`}>
                    {STATUS_LABEL[p.status] ?? p.status}
                  </span>
                </div>
              ))}
            </div>
          )}
        </section>
      </div>
    </>
  );
}
