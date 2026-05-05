import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { X, Shield } from 'lucide-react';

import { apiGet } from '@/lib/api';
import { LangSwitcher } from './LangSwitcher';

interface SideMenuProps {
  open: boolean;
  onClose: () => void;
}

const DOC_TYPES = [
  { key: 'article',     emoji: '📄', i18n: 'docTypes.article' },
  { key: 'taqdimot',    emoji: '🎯', i18n: 'docTypes.taqdimot' },
  { key: 'coursework',  emoji: '📚', i18n: 'docTypes.coursework' },
  { key: 'independent', emoji: '📝', i18n: 'docTypes.independent' },
  { key: 'thesis',      emoji: '📌', i18n: 'docTypes.thesis' },
  { key: 'diploma',     emoji: '🎓', i18n: 'docTypes.diploma' },
  { key: 'dissertation',emoji: '🔬', i18n: 'docTypes.dissertation' },
  { key: 'manual',      emoji: '📖', i18n: 'docTypes.manual' },
];

export function SideMenu({ open, onClose }: SideMenuProps) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [role, setRole] = useState<string>('');

  useEffect(() => {
    if (!open) return;
    apiGet<{ role: string }>('/users/me').then((u) => setRole(u.role)).catch(() => null);
  }, [open]);

  const isAdmin = role === 'admin' || role === 'superadmin';

  // Lock body scroll while open
  useEffect(() => {
    if (open) {
      const prev = document.body.style.overflow;
      document.body.style.overflow = 'hidden';
      return () => { document.body.style.overflow = prev; };
    }
  }, [open]);

  // Close on Escape
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  if (!open) return null;

  function pick(type: string) {
    onClose();
    navigate(`/orders/new?type=${type}`);
  }

  return (
    <div className="fixed inset-0 z-[60]">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/50 backdrop-blur-sm animate-fade-in"
        onClick={onClose}
      />
      {/* Drawer */}
      <aside
        className="absolute top-0 right-0 h-full w-72 max-w-[85vw] bg-white shadow-2xl flex flex-col animate-slide-in-right"
      >
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-slate-200">
          <h2 className="font-bold text-slate-900">{t('newOrder.title')}</h2>
          <button
            onClick={onClose}
            className="w-8 h-8 grid place-items-center rounded-lg hover:bg-slate-100"
            aria-label="Close menu"
          >
            <X size={18} />
          </button>
        </div>

        {/* Doc types */}
        <div className="flex-1 overflow-y-auto py-2">
          <p className="px-4 py-2 text-xs uppercase tracking-wide text-slate-400">
            {t('newOrder.selectType')}
          </p>
          {DOC_TYPES.map((d) => (
            <button
              key={d.key}
              onClick={() => pick(d.key)}
              className="flex items-center gap-3 w-full text-left px-4 py-2.5 hover:bg-slate-50 transition"
            >
              <span className="text-xl shrink-0">{d.emoji}</span>
              <span className="text-sm font-medium">{t(d.i18n)}</span>
            </button>
          ))}
        </div>

        {/* Footer: optional admin link + language switcher */}
        <div className="border-t border-slate-200 p-4 space-y-3">
          {isAdmin && (
            <button
              onClick={() => { onClose(); navigate('/admin'); }}
              className="w-full flex items-center justify-center gap-2 px-3 py-2.5 rounded-xl bg-gradient-to-br from-violet-500 to-purple-700 text-white font-medium text-sm hover:opacity-95"
            >
              <Shield size={16} /> {t('nav.admin')}
            </button>
          )}
          <div>
            <p className="text-xs uppercase tracking-wide text-slate-400 mb-2">
              Til / Language
            </p>
            <LangSwitcher />
          </div>
        </div>
      </aside>
    </div>
  );
}
