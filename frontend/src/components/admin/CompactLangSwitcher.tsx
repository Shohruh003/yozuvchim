import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Check, ChevronDown, Globe } from 'lucide-react';

const LANGS = [
  { code: 'uz', label: "O'zbekcha", flag: '/uz.svg' },
  { code: 'ru', label: 'Русский',   flag: '/ru.svg' },
  { code: 'en', label: 'English',   flag: '/en.svg' },
];

export function CompactLangSwitcher() {
  const { i18n } = useTranslation();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const current = LANGS.find((l) => l.code === i18n.resolvedLanguage) || LANGS[0];

  useEffect(() => {
    function onClick(e: MouseEvent) {
      if (open && ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    window.addEventListener('mousedown', onClick);
    return () => window.removeEventListener('mousedown', onClick);
  }, [open]);

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen((s) => !s)}
        className="inline-flex items-center gap-2 px-2.5 py-1.5 rounded-lg hover:bg-slate-100 text-sm text-slate-600 transition"
      >
        <img src={current.flag} alt="" className="w-5 h-5 rounded-full object-cover ring-1 ring-slate-200" />
        <span className="hidden sm:inline">{current.code.toUpperCase()}</span>
        <ChevronDown size={14} className="text-slate-400" />
      </button>

      {open && (
        <div className="absolute left-0 right-0 bottom-full mb-2 bg-white rounded-xl border border-slate-200 shadow-lg overflow-hidden z-50">
          <div className="px-3 py-2 text-[11px] uppercase tracking-wide text-slate-400 font-semibold flex items-center gap-1.5 border-b border-slate-100">
            <Globe size={12} /> Til / Language
          </div>
          {LANGS.map((lang) => {
            const active = lang.code === i18n.resolvedLanguage;
            return (
              <button
                key={lang.code}
                onClick={() => {
                  i18n.changeLanguage(lang.code);
                  setOpen(false);
                }}
                className={
                  'w-full flex items-center gap-3 px-3 py-2.5 text-sm transition ' +
                  (active ? 'bg-brand-50 text-brand-700 font-medium' : 'text-slate-700 hover:bg-slate-50')
                }
              >
                <img src={lang.flag} alt="" className="w-5 h-5 rounded-full object-cover ring-1 ring-slate-200" />
                <span className="flex-1 text-left">{lang.label}</span>
                {active && <Check size={14} className="text-brand-600" />}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
