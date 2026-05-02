import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Globe, X, Check } from 'lucide-react';

import { cn } from '@/lib/utils';

const LANGS = [
  { code: 'uz', label: "O'zbekcha", flag: '/uz.svg' },
  { code: 'ru', label: 'Русский',   flag: '/ru.svg' },
  { code: 'en', label: 'English',   flag: '/en.svg' },
];

const TITLE: Record<string, string> = {
  uz: 'Tilni tanlang',
  ru: 'Выберите язык',
  en: 'Choose language',
};
const CONFIRM: Record<string, string> = {
  uz: 'Tanlash',
  ru: 'Выбрать',
  en: 'Select',
};

/** Trigger button + bottom sheet picker. Used inside the side drawer. */
export function LangSwitcher() {
  const { i18n } = useTranslation();
  const [open, setOpen] = useState(false);
  const [selected, setSelected] = useState(i18n.resolvedLanguage || 'uz');
  const current = LANGS.find((l) => l.code === i18n.resolvedLanguage) || LANGS[0];

  function confirm() {
    i18n.changeLanguage(selected);
    setOpen(false);
  }

  return (
    <>
      <button
        onClick={() => {
          setSelected(i18n.resolvedLanguage || 'uz');
          setOpen(true);
        }}
        className="flex items-center gap-2 w-full px-3 py-2.5 rounded-xl text-sm font-medium text-slate-700 hover:bg-slate-50 transition border border-slate-200"
      >
        <img src={current.flag} alt="" className="w-5 h-5 rounded-full object-cover ring-1 ring-slate-200" />
        <span className="flex-1 text-left">Til: {current.label}</span>
        <Globe size={14} className="text-slate-400" />
      </button>

      {open && (
        <div className="fixed inset-0 z-[100]" onClick={() => setOpen(false)}>
          <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" />
          <div
            className="absolute bottom-0 left-0 right-0 bg-white rounded-t-3xl animate-slide-up"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Drag handle */}
            <div className="flex justify-center pt-3 pb-1">
              <div className="w-10 h-1 rounded-full bg-slate-300" />
            </div>
            {/* Header */}
            <div className="flex items-center justify-between px-5 py-3">
              <h3 className="text-lg font-bold text-slate-900">
                {TITLE[i18n.resolvedLanguage || 'uz']}
              </h3>
              <button
                onClick={() => setOpen(false)}
                className="p-1.5 rounded-full hover:bg-slate-100 text-slate-400"
                aria-label="Close"
              >
                <X size={20} />
              </button>
            </div>
            {/* Options */}
            <div className="px-5 pb-3 space-y-2">
              {LANGS.map((lang) => (
                <button
                  key={lang.code}
                  onClick={() => setSelected(lang.code)}
                  className={cn(
                    'flex items-center justify-between w-full px-4 py-3.5 rounded-2xl border-2 transition-all',
                    selected === lang.code
                      ? 'border-brand-500 bg-brand-50'
                      : 'border-slate-200',
                  )}
                >
                  <div className="flex items-center gap-3">
                    <img
                      src={lang.flag}
                      alt=""
                      className="w-8 h-8 rounded-full object-cover ring-1 ring-slate-200"
                    />
                    <span
                      className={cn(
                        'text-sm font-medium',
                        selected === lang.code ? 'text-brand-700' : 'text-slate-700',
                      )}
                    >
                      {lang.label}
                    </span>
                  </div>
                  <div
                    className={cn(
                      'w-5 h-5 rounded-full border-2 flex items-center justify-center',
                      selected === lang.code
                        ? 'border-brand-500 bg-brand-500'
                        : 'border-slate-300',
                    )}
                  >
                    {selected === lang.code && <Check size={12} className="text-white" />}
                  </div>
                </button>
              ))}
            </div>
            <div className="px-5 pb-8 pt-2">
              <button
                onClick={confirm}
                className="w-full py-3.5 rounded-2xl bg-brand-500 hover:bg-brand-600 text-white font-semibold"
              >
                {CONFIRM[i18n.resolvedLanguage || 'uz']}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
