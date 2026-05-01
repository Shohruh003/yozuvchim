import { useTranslation } from 'react-i18next';

const LANGS: { code: string; label: string }[] = [
  { code: 'uz', label: 'O\'Z' },
  { code: 'ru', label: 'RU' },
  { code: 'en', label: 'EN' },
];

export function LangSwitcher() {
  const { i18n } = useTranslation();
  const current = i18n.resolvedLanguage || 'uz';

  return (
    <div className="flex items-center gap-0.5 rounded-lg border border-slate-200 bg-white p-0.5 text-[11px]">
      {LANGS.map((l) => (
        <button
          key={l.code}
          onClick={() => i18n.changeLanguage(l.code)}
          className={
            'px-2 py-1 rounded ' +
            (current === l.code
              ? 'bg-brand-500 text-white font-semibold'
              : 'text-slate-500 hover:bg-slate-100')
          }
        >
          {l.label}
        </button>
      ))}
    </div>
  );
}
