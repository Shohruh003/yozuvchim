import { NavLink, Outlet } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

import { cn } from '@/lib/utils';
import { LangSwitcher } from './LangSwitcher';

const linkBase = 'px-2 sm:px-3 py-1.5 rounded-lg text-xs sm:text-sm transition';
const linkInactive = 'hover:bg-slate-100';
const linkActive = 'bg-brand-100 text-brand-700 font-semibold';

export function Layout() {
  const { t } = useTranslation();
  return (
    <div className="min-h-screen">
      <nav className="bg-white/90 backdrop-blur sticky top-0 z-30 border-b border-slate-200">
        <div className="max-w-6xl mx-auto px-3 py-2.5 flex items-center justify-between gap-2">
          <NavLink to="/profile" className="flex items-center gap-2 font-bold text-brand-700 shrink-0">
            <span className="w-7 h-7 grid place-items-center rounded-lg bg-brand-500 text-white text-sm">
              Y
            </span>
            <span>Yozuvchim</span>
          </NavLink>
          <div className="flex items-center gap-2">
            <NavLink to="/profile" className={({ isActive }) => cn(linkBase, isActive ? linkActive : linkInactive)}>
              {t('nav.profile')}
            </NavLink>
            <NavLink to="/orders" className={({ isActive }) => cn(linkBase, isActive ? linkActive : linkInactive)}>
              {t('nav.orders')}
            </NavLink>
            <LangSwitcher />
          </div>
        </div>
      </nav>

      <main className="max-w-6xl mx-auto px-3 sm:px-4 py-4 sm:py-6">
        <Outlet />
      </main>
    </div>
  );
}
