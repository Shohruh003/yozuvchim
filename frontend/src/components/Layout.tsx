import { useState } from 'react';
import { NavLink, Outlet } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Menu } from 'lucide-react';

import { cn } from '@/lib/utils';
import { SideMenu } from './SideMenu';

const linkBase = 'px-2 sm:px-3 py-1.5 rounded-lg text-xs sm:text-sm transition shrink-0';
const linkInactive = 'hover:bg-slate-100';
const linkActive = 'bg-brand-100 text-brand-700 font-semibold';

export function Layout() {
  const { t } = useTranslation();
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <div className="min-h-screen overflow-x-hidden">
      <nav className="bg-white/90 backdrop-blur sticky top-0 z-30 border-b border-slate-200">
        <div className="max-w-6xl mx-auto px-3 py-2 flex items-center justify-between gap-2">
          <NavLink to="/profile" className="flex items-center gap-2 font-bold text-brand-700 shrink-0">
            <span className="w-7 h-7 grid place-items-center rounded-lg bg-brand-500 text-white text-sm">
              Y
            </span>
            <span>Yozuvchim</span>
          </NavLink>

          <div className="flex items-center gap-1">
            <NavLink
              to="/profile"
              className={({ isActive }) => cn(linkBase, isActive ? linkActive : linkInactive)}
            >
              {t('nav.profile')}
            </NavLink>
            <NavLink
              to="/orders"
              className={({ isActive }) => cn(linkBase, isActive ? linkActive : linkInactive)}
            >
              {t('nav.orders')}
            </NavLink>
            <button
              onClick={() => setMenuOpen(true)}
              className="ml-1 w-9 h-9 grid place-items-center rounded-lg hover:bg-slate-100 transition"
              aria-label="Open menu"
            >
              <Menu size={20} />
            </button>
          </div>
        </div>
      </nav>

      <main className="max-w-6xl mx-auto px-3 sm:px-4 py-4 sm:py-6">
        <Outlet />
      </main>

      <SideMenu open={menuOpen} onClose={() => setMenuOpen(false)} />
    </div>
  );
}
