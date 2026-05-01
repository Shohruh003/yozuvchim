import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import toast from 'react-hot-toast';

import { apiGet, apiPost } from '@/lib/api';

type DocKey =
  | 'article'
  | 'taqdimot'
  | 'coursework'
  | 'independent'
  | 'thesis';

interface DocType {
  key: DocKey;
  label: string;
  emoji: string;
  fields: string[];
}

const DOC_TYPES: DocType[] = [
  { key: 'article',     label: 'Maqola',       emoji: '📄', fields: ['topic', 'language', 'length'] },
  { key: 'taqdimot',    label: 'Taqdimot',     emoji: '🎯', fields: ['topic', 'language', 'length', 'ppt_style', 'ppt_template'] },
  { key: 'coursework',  label: 'Kurs ishi',    emoji: '📚', fields: ['topic', 'language', 'length', 'subject', 'uni'] },
  { key: 'independent', label: 'Mustaqil ish', emoji: '📝', fields: ['topic', 'language', 'length', 'subject', 'uni'] },
  { key: 'thesis',      label: 'Tezis',        emoji: '📌', fields: ['topic', 'language', 'length'] },
];

interface TemplateMeta {
  key: string;
  label: string;
  description: string;
  image_url: string;
}

export default function NewOrderPage() {
  const navigate = useNavigate();
  const [picked, setPicked] = useState<DocType | null>(null);
  const [templates, setTemplates] = useState<TemplateMeta[]>([]);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (picked?.fields.includes('ppt_template') && templates.length === 0) {
      apiGet<TemplateMeta[]>('/templates').then(setTemplates);
    }
  }, [picked, templates.length]);

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!picked) return;
    const fd = new FormData(e.currentTarget);
    const payload: Record<string, any> = { doc_type: picked.key };
    for (const [k, v] of fd.entries()) {
      if (typeof v === 'string' && v.trim()) payload[k] = v;
    }
    setSubmitting(true);
    try {
      const r = await apiPost<{ id: number }>('/orders', payload);
      toast.success('Buyurtma yaratildi');
      navigate(`/orders/${r.id}`);
    } catch (err: any) {
      toast.error(err?.response?.data?.message || 'Xato');
      setSubmitting(false);
    }
  }

  if (!picked) {
    return (
      <>
        <div className="mb-4">
          <h1 className="text-xl sm:text-2xl font-bold">Yangi buyurtma</h1>
          <p className="text-sm text-slate-500 mt-1">Hujjat turini tanlang</p>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
          {DOC_TYPES.map((t) => (
            <button
              key={t.key}
              onClick={() => setPicked(t)}
              className="flex flex-col items-center gap-2 text-center p-4 bg-white rounded-2xl border border-slate-200 hover:border-brand-400 hover:shadow-md transition"
            >
              <div className="text-3xl">{t.emoji}</div>
              <div className="font-semibold text-sm sm:text-base">{t.label}</div>
            </button>
          ))}
        </div>
      </>
    );
  }

  return (
    <>
      <button onClick={() => setPicked(null)} className="text-brand-600 text-sm mb-4">
        ← Ortga
      </button>
      <h2 className="text-lg font-semibold mb-3">
        {picked.emoji} {picked.label}
      </h2>

      <form onSubmit={onSubmit} className="bg-white rounded-2xl border border-slate-200 p-6 space-y-4">
        <div>
          <label className="block text-sm font-medium mb-1">Mavzu / sarlavha</label>
          <input
            type="text"
            name="title"
            required
            placeholder="Mavzuni kiriting..."
            className="w-full border border-slate-300 rounded-xl px-4 py-2.5 focus:ring-2 focus:ring-brand-500 focus:border-brand-500 outline-none"
          />
        </div>

        <div className="grid sm:grid-cols-2 gap-3">
          <div>
            <label className="block text-sm font-medium mb-1">Til</label>
            <select name="language" defaultValue="uz" className="w-full border border-slate-300 rounded-xl px-4 py-2.5">
              <option value="uz">O'zbekcha</option>
              <option value="ru">Русский</option>
              <option value="en">English</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">
              Hajm (bet/slayd)
            </label>
            <input
              type="number"
              name="length"
              min={1}
              max={50}
              defaultValue={5}
              className="w-full border border-slate-300 rounded-xl px-4 py-2.5"
            />
          </div>
        </div>

        {picked.fields.includes('subject') && (
          <div>
            <label className="block text-sm font-medium mb-1">Fan</label>
            <input type="text" name="subject" className="w-full border border-slate-300 rounded-xl px-4 py-2.5" />
          </div>
        )}

        {picked.fields.includes('ppt_style') && (
          <div>
            <label className="block text-sm font-medium mb-2">Taqdimot uslubi</label>
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
                    {s === 'akademik' ? '🏛 Akademik' : s === 'biznes' ? '💼 Biznes' : '🎨 Kreativ'}
                  </span>
                </label>
              ))}
            </div>
          </div>
        )}

        {picked.fields.includes('ppt_template') && (
          <div>
            <label className="block text-sm font-medium mb-2">Slayd shabloni</label>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 sm:gap-3">
              {templates.map((t, i) => (
                <label key={t.key} className="cursor-pointer block">
                  <input
                    type="radio"
                    name="ppt_template"
                    value={t.key}
                    defaultChecked={i === 0}
                    className="peer sr-only"
                  />
                  <div className="rounded-xl overflow-hidden border-2 border-slate-200 peer-checked:border-brand-500 peer-checked:ring-2 peer-checked:ring-brand-200 transition">
                    <div className="aspect-video bg-slate-100">
                      <img
                        src={t.image_url}
                        loading="lazy"
                        alt={t.label}
                        className="w-full h-full object-cover"
                        onError={(e) => ((e.target as HTMLImageElement).style.display = 'none')}
                      />
                    </div>
                    <div className="p-2 bg-white">
                      <div className="text-xs sm:text-sm font-medium truncate">{t.label}</div>
                      <div className="text-[10px] sm:text-xs text-slate-500 truncate">{t.description}</div>
                    </div>
                  </div>
                </label>
              ))}
            </div>
          </div>
        )}

        <button
          type="submit"
          disabled={submitting}
          className="w-full px-5 py-3 rounded-xl bg-brand-500 text-white font-semibold hover:bg-brand-600 disabled:opacity-50"
        >
          {submitting ? 'Yuborilmoqda...' : 'Buyurtma berish'}
        </button>
      </form>
    </>
  );
}
