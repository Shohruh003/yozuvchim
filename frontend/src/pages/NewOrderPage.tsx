import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Sparkles, Wallet } from 'lucide-react';
import toast from 'react-hot-toast';

import { apiGet, apiPost } from '@/lib/api';
import { formatNumber } from '@/lib/utils';

type DocKey =
  | 'article'
  | 'taqdimot'
  | 'coursework'
  | 'independent'
  | 'thesis'
  | 'diploma'
  | 'dissertation'
  | 'manual';

interface DocType {
  key: DocKey;
  i18n: string;       // i18n key under docTypes.*
  emoji: string;
  fields: string[];
}

const DOC_TYPES: DocType[] = [
  { key: 'article',      i18n: 'docTypes.article',      emoji: '📄', fields: ['topic', 'language', 'length'] },
  { key: 'taqdimot',     i18n: 'docTypes.taqdimot',     emoji: '🎯', fields: ['topic', 'language', 'length', 'ppt_style', 'ppt_template'] },
  { key: 'coursework',   i18n: 'docTypes.coursework',   emoji: '📚', fields: ['topic', 'language', 'length', 'subject', 'uni'] },
  { key: 'independent',  i18n: 'docTypes.independent',  emoji: '📝', fields: ['topic', 'language', 'length', 'subject', 'uni'] },
  { key: 'thesis',       i18n: 'docTypes.thesis',       emoji: '📌', fields: ['topic', 'language', 'length'] },
  { key: 'diploma',      i18n: 'docTypes.diploma',      emoji: '🎓', fields: ['topic', 'language', 'length', 'subject', 'uni'] },
  { key: 'dissertation', i18n: 'docTypes.dissertation', emoji: '🔬', fields: ['topic', 'language', 'length', 'subject', 'uni'] },
  { key: 'manual',       i18n: 'docTypes.manual',       emoji: '📖', fields: ['topic', 'language', 'length', 'subject'] },
];

interface TemplateMeta {
  key: string;
  label: string;
  description: string;
  image_url: string;
}

export default function NewOrderPage() {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const [params] = useSearchParams();
  const initialType = useMemo(() => {
    const t = params.get('type');
    return DOC_TYPES.find((d) => d.key === t) ?? null;
  }, [params]);
  const [picked, setPicked] = useState<DocType | null>(initialType);
  const [templates, setTemplates] = useState<TemplateMeta[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [length, setLength] = useState(5);
  const [quote, setQuote] = useState<{ price: number } | null>(null);
  const [me, setMe] = useState<{ balance: number; has_used_free_trial: boolean } | null>(null);

  useEffect(() => {
    apiGet<{ balance: number; has_used_free_trial: boolean }>('/users/me')
      .then(setMe)
      .catch(() => null);
  }, []);

  useEffect(() => {
    if (picked?.fields.includes('ppt_template') && templates.length === 0) {
      apiGet<TemplateMeta[]>('/templates').then(setTemplates);
    }
  }, [picked, templates.length]);

  useEffect(() => {
    if (!picked) {
      setQuote(null);
      return;
    }
    apiGet<{ price: number }>(`/orders/quote?doc_type=${picked.key}&length=${length}`)
      .then(setQuote)
      .catch(() => setQuote(null));
  }, [picked, length]);

  // sync URL when user navigates back/forward or selects from menu
  useEffect(() => {
    if (initialType && (!picked || picked.key !== initialType.key)) {
      setPicked(initialType);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialType?.key]);

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!picked) return;
    const fd = new FormData(e.currentTarget);
    const payload: Record<string, any> = {
      doc_type: picked.key,
      expected_price: quote?.price,   // matches what the user sees on screen
    };
    for (const [k, v] of fd.entries()) {
      if (typeof v === 'string' && v.trim()) payload[k] = v;
    }
    setSubmitting(true);
    try {
      const r = await apiPost<{ id: number }>('/orders', payload);
      toast.success(t('newOrder.created'));
      navigate(`/orders/${r.id}`);
    } catch (err: any) {
      toast.error(err?.response?.data?.message || t('newOrder.error'));
      setSubmitting(false);
    }
  }

  if (!picked) {
    return (
      <>
        <div className="mb-4">
          <h1 className="text-xl sm:text-2xl font-bold">{t('newOrder.title')}</h1>
          <p className="text-sm text-slate-500 mt-1">{t('newOrder.selectType')}</p>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
          {DOC_TYPES.map((d) => (
            <button
              key={d.key}
              onClick={() => setPicked(d)}
              className="flex flex-col items-center gap-2 text-center p-4 bg-white rounded-2xl border border-slate-200 hover:border-brand-400 hover:shadow-md transition"
            >
              <div className="text-3xl">{d.emoji}</div>
              <div className="font-semibold text-sm sm:text-base">{t(d.i18n)}</div>
            </button>
          ))}
        </div>
      </>
    );
  }

  return (
    <>
      <button onClick={() => setPicked(null)} className="text-brand-600 text-sm mb-4">
        {t('newOrder.back')}
      </button>
      <h2 className="text-lg font-semibold mb-3">
        {picked.emoji} {t(picked.i18n)}
      </h2>

      <form onSubmit={onSubmit} className="bg-white rounded-2xl border border-slate-200 p-6 space-y-4">
        <div>
          <label className="block text-sm font-medium mb-1">{t('newOrder.topic')}</label>
          <input
            type="text"
            name="title"
            required
            placeholder={t('newOrder.topicPlaceholder')}
            className="w-full border border-slate-300 rounded-xl px-4 py-2.5 focus:ring-2 focus:ring-brand-500 focus:border-brand-500 outline-none"
          />
        </div>

        <div className="grid sm:grid-cols-2 gap-3">
          <div>
            <label className="block text-sm font-medium mb-1">{t('newOrder.language')}</label>
            <select name="language" defaultValue="uz" className="w-full border border-slate-300 rounded-xl px-4 py-2.5">
              <option value="uz">O'zbekcha</option>
              <option value="ru">Русский</option>
              <option value="en">English</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">{t('newOrder.size')}</label>
            <input
              type="number"
              name="length"
              min={1}
              max={50}
              value={length}
              onChange={(e) => setLength(Math.max(1, Math.min(50, Number(e.target.value) || 1)))}
              className="w-full border border-slate-300 rounded-xl px-4 py-2.5"
            />
          </div>
        </div>

        {picked.fields.includes('subject') && (
          <div>
            <label className="block text-sm font-medium mb-1">{t('newOrder.subject')}</label>
            <input type="text" name="subject" className="w-full border border-slate-300 rounded-xl px-4 py-2.5" />
          </div>
        )}

        {picked.fields.includes('ppt_style') && (
          <div>
            <label className="block text-sm font-medium mb-2">{t('newOrder.presentationStyle')}</label>
            <div className="flex gap-2 flex-wrap">
              {(['akademik', 'biznes', 'kreativ'] as const).map((s, i) => (
                <label key={s} className="cursor-pointer">
                  <input
                    type="radio"
                    name="ppt_style"
                    value={s}
                    defaultChecked={i === 0}
                    className="peer sr-only"
                  />
                  <span className="px-4 py-2 rounded-xl border border-slate-300 peer-checked:bg-brand-500 peer-checked:text-white peer-checked:border-brand-500 inline-block">
                    {t(`pptStyle.${s}`)}
                  </span>
                </label>
              ))}
            </div>
          </div>
        )}

        {picked.fields.includes('ppt_template') && (
          <div>
            <label className="block text-sm font-medium mb-2">{t('newOrder.slideTemplate')}</label>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 sm:gap-3">
              {templates.map((tpl, i) => (
                <label key={tpl.key} className="cursor-pointer block">
                  <input
                    type="radio"
                    name="ppt_template"
                    value={tpl.key}
                    defaultChecked={i === 0}
                    className="peer sr-only"
                  />
                  <div className="rounded-xl overflow-hidden border-2 border-slate-200 peer-checked:border-brand-500 peer-checked:ring-2 peer-checked:ring-brand-200 transition">
                    <div className="aspect-video bg-slate-100">
                      <img
                        src={tpl.image_url}
                        loading="lazy"
                        alt={tpl.label}
                        className="w-full h-full object-cover"
                        onError={(e) => ((e.target as HTMLImageElement).style.display = 'none')}
                      />
                    </div>
                    <div className="p-2 bg-white">
                      <div className="text-xs sm:text-sm font-medium truncate">{tpl.label}</div>
                      <div className="text-[10px] sm:text-xs text-slate-500 truncate">{tpl.description}</div>
                    </div>
                  </div>
                </label>
              ))}
            </div>
          </div>
        )}

        {/* Price + balance summary */}
        {(() => {
          if (!me) return null;
          const willUseFreeTrial = !me.has_used_free_trial;
          const price = quote?.price ?? 0;
          const finalPrice = willUseFreeTrial ? 0 : price;
          const insufficient = !willUseFreeTrial && me.balance < price;

          return (
            <div className="rounded-2xl border border-slate-200 bg-gradient-to-br from-slate-50 to-white p-4 space-y-3">
              {willUseFreeTrial && (
                <div className="flex items-center gap-2 px-3 py-2 rounded-xl bg-emerald-50 text-emerald-800 text-sm border border-emerald-200">
                  <Sparkles size={16} />
                  <span className="font-medium">{t('newOrder.freeTrialBadge')}</span>
                </div>
              )}
              <div className="flex items-center justify-between">
                <span className="text-sm text-slate-500">{t('newOrder.priceLabel')}</span>
                <span className="text-lg font-bold">
                  {willUseFreeTrial ? (
                    <>
                      <span className="line-through text-slate-400 text-base font-normal mr-2">
                        {formatNumber(price)} so'm
                      </span>
                      <span className="text-emerald-600">0 so'm</span>
                    </>
                  ) : quote === null ? (
                    <span className="text-slate-400 text-sm font-normal">{t('newOrder.calculating')}</span>
                  ) : (
                    <>{formatNumber(finalPrice)} so'm</>
                  )}
                </span>
              </div>
              <div className="flex items-center justify-between text-sm">
                <span className="text-slate-500 flex items-center gap-1.5">
                  <Wallet size={14} /> {t('newOrder.balanceLabel')}
                </span>
                <span className={insufficient ? 'text-rose-600 font-semibold' : 'text-slate-700'}>
                  {formatNumber(me.balance)} so'm
                </span>
              </div>
              {insufficient && (
                <Link
                  to="/payments"
                  className="block text-center w-full py-2.5 rounded-xl bg-amber-100 text-amber-800 hover:bg-amber-200 text-sm font-semibold border border-amber-200"
                >
                  {t('newOrder.topUpBalance')}
                </Link>
              )}
            </div>
          );
        })()}

        <button
          type="submit"
          disabled={submitting || (me ? !me.has_used_free_trial ? false : (quote && me.balance < quote.price) || false : false)}
          className="w-full px-5 py-3 rounded-xl bg-brand-500 text-white font-semibold hover:bg-brand-600 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {submitting ? t('newOrder.submitting') : t('newOrder.submit')}
        </button>
      </form>
    </>
  );
}
