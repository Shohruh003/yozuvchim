import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { CreditCard, Copy, Check } from 'lucide-react';
import toast from 'react-hot-toast';

import { apiGet } from '@/lib/api';
import { formatNumber } from '@/lib/utils';

interface CardItem {
  id: number;
  number: string;
  holder: string;
  bank: string;
}

interface PaymentInfo {
  currency: string;
  cards: CardItem[];
}

interface PaymentRow {
  id: number;
  amount: number;
  status: string;
  created_at: string;
}

const STATUS_COLOR: Record<string, string> = {
  approved: 'text-emerald-600',
  pending: 'text-amber-600',
  rejected: 'text-rose-600',
};

export default function PaymentsPage() {
  const { t, i18n } = useTranslation();
  const [info, setInfo] = useState<PaymentInfo | null>(null);
  const [history, setHistory] = useState<PaymentRow[] | null>(null);

  useEffect(() => {
    apiGet<PaymentInfo>('/payments/info').then(setInfo).catch(() => null);
    apiGet<PaymentRow[]>('/payments/history').then(setHistory).catch(() => setHistory([]));
  }, []);

  const fmtDate = (s: string) =>
    new Date(s).toLocaleString(i18n.language === 'ru' ? 'ru-RU' : 'uz-UZ', {
      day: '2-digit', month: 'short', year: 'numeric',
      hour: '2-digit', minute: '2-digit',
    });

  return (
    <>
      <h1 className="text-xl sm:text-2xl font-bold mb-5">{t('payments.title')}</h1>

      <div className="grid md:grid-cols-2 gap-5">
        <section>
          <h3 className="font-semibold mb-3 text-slate-700">{t('payments.info')}</h3>

          {info === null ? (
            <div className="bg-white rounded-2xl border border-slate-200 p-6 text-slate-400 text-sm">
              {t('common.loading')}
            </div>
          ) : info.cards.length === 0 ? (
            <div className="bg-amber-50 rounded-2xl border border-amber-200 p-6 text-amber-800 text-sm">
              {t('payments.noCards')}
            </div>
          ) : (
            <div className="space-y-3">
              {info.cards.map((c) => (
                <PaymentCard key={c.id} card={c} />
              ))}
            </div>
          )}

          <div className="mt-4 p-4 bg-amber-50 rounded-xl text-sm text-amber-800 border border-amber-200">
            {t('payments.instruction')}
          </div>
        </section>

        <section className="bg-white rounded-2xl border border-slate-200 p-6">
          <h3 className="font-semibold mb-4">{t('payments.history')}</h3>
          {history === null ? (
            <div className="text-slate-400 text-sm">{t('common.loading')}</div>
          ) : history.length === 0 ? (
            <div className="text-slate-400 text-sm">{t('payments.empty')}</div>
          ) : (
            <div className="space-y-2">
              {history.map((p) => (
                <div
                  key={p.id}
                  className="flex items-center justify-between p-3 rounded-xl border border-slate-100"
                >
                  <div>
                    <div className="font-semibold">{formatNumber(p.amount)} so'm</div>
                    <div className="text-xs text-slate-500">{fmtDate(p.created_at)}</div>
                  </div>
                  <span className={`text-sm font-medium ${STATUS_COLOR[p.status] ?? ''}`}>
                    {t(`payments.status.${p.status}`, p.status)}
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

function PaymentCard({ card }: { card: CardItem }) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(card.number.replace(/\s+/g, ''));
      setCopied(true);
      toast.success('Karta raqami nusxalandi');
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      toast.error('Nusxalab bo\'lmadi');
    }
  }

  const formatted = card.number.replace(/\s+/g, '').replace(/(.{4})/g, '$1 ').trim();

  return (
    <div className="rounded-2xl border-transparent shadow-lg bg-gradient-to-br from-indigo-500 via-purple-600 to-fuchsia-600 text-white p-5 relative overflow-hidden">
      <div className="flex items-start justify-between">
        <CreditCard size={28} className="opacity-80" />
        {card.bank && (
          <span className="text-[10px] uppercase tracking-wide font-semibold px-2 py-0.5 rounded-full bg-white/15">
            {card.bank}
          </span>
        )}
      </div>
      <button
        onClick={copy}
        className="mt-6 group flex items-center gap-2 text-2xl sm:text-2xl font-mono font-bold tracking-wider hover:opacity-90 transition"
      >
        {formatted}
        {copied ? (
          <Check size={18} className="text-emerald-300" />
        ) : (
          <Copy size={16} className="opacity-60 group-hover:opacity-100" />
        )}
      </button>
      <div className="mt-3 text-xs text-white/70 uppercase tracking-wide">Egasi</div>
      <div className="font-semibold">{card.holder}</div>
    </div>
  );
}
