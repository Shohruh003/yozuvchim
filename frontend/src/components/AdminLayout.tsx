import { useEffect, useState } from 'react';
import { NavLink, Outlet } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import {
  LayoutDashboard,
  Users,
  CreditCard,
  Menu as MenuIcon,
  X,
  ReceiptText,
  Shield,
  CreditCard as CardIcon,
  Settings as SettingsIcon,
  type LucideIcon,
} from 'lucide-react';

import { cn } from '@/lib/utils';
import { apiGet } from '@/lib/api';
import { useAuthStore } from '@/stores/auth';
import { CompactLangSwitcher } from './admin/CompactLangSwitcher';

interface NavItem {
  to: string;
  i18n: string;
  icon: LucideIcon;
  superadminOnly?: boolean;
}

const NAV: NavItem[] = [
  { to: '/admin',              i18n: 'admin.nav.dashboard',    icon: LayoutDashboard },
  { to: '/admin/users',        i18n: 'admin.nav.users',        icon: Users },
  { to: '/admin/payments',     i18n: 'admin.nav.payments',     icon: CreditCard },
  { to: '/admin/transactions', i18n: 'admin.nav.transactions', icon: ReceiptText },
  { to: '/admin/cards',        i18n: 'admin.nav.cards',        icon: CardIcon },
  { to: '/admin/admins',       i18n: 'admin.nav.admins',       icon: Shield, superadminOnly: true },
  { to: '/admin/settings',     i18n: 'admin.nav.settings',     icon: SettingsIcon, superadminOnly: true },
];

const SIDEBAR_KEY = 'yozuvchim_admin_sidebar';

export function AdminLayout() {
  const { t } = useTranslation();
  const [sidebarOpen, setSidebarOpen] = useState<boolean>(() => {
    if (typeof window === 'undefined') return true;
    const v = window.localStorage.getItem(SIDEBAR_KEY);
    return v === null ? true : v === '1';
  });
  const [role, setRole] = useState<string>('');

  useEffect(() => {
    apiGet<{ role: string }>('/users/me').then((u) => setRole(u.role)).catch(() => null);
  }, []);

  useEffect(() => {
    window.localStorage.setItem(SIDEBAR_KEY, sidebarOpen ? '1' : '0');
  }, [sidebarOpen]);

  const visibleNav = NAV.filter((n) => !n.superadminOnly || role === 'superadmin');

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Top bar */}
      <header className="bg-white border-b border-slate-200 sticky top-0 z-50">
        <div className="px-3 sm:px-4 py-3 flex items-center gap-3">
          <button
            onClick={() => setSidebarOpen((s) => !s)}
            className="w-9 h-9 grid place-items-center rounded-lg hover:bg-slate-100 transition"
            aria-label="Toggle menu"
          >
            <MenuIcon size={18} />
          </button>
          <div className="flex items-center gap-2 font-bold text-brand-700">
            <span className="w-7 h-7 grid place-items-center rounded-lg bg-gradient-to-br from-brand-500 to-brand-700 text-white text-xs">
              A
            </span>
            <span>{t('admin.title')}</span>
          </div>
          <div className="ml-auto">
            <button
              onClick={() => {
                useAuthStore.getState().clear();
                window.location.href = '/admin/login';
              }}
              className="text-sm text-slate-500 hover:text-rose-600 px-2.5 py-1.5 rounded-lg hover:bg-rose-50 transition"
              title={t('admin.logout')}
            >
              {t('admin.logout')}
            </button>
          </div>
        </div>
      </header>

      {/* Mobile backdrop (only when open and small screen) */}
      {sidebarOpen && (
        <div
          className="lg:hidden fixed inset-0 top-[57px] bg-black/40 backdrop-blur-sm animate-fade-in z-30"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar — overlay-style, slides in/out */}
      <aside
        className={cn(
          'fixed top-[57px] left-0 z-40 w-64 bg-white border-r border-slate-200 h-[calc(100vh-57px)] flex flex-col transition-transform duration-200 ease-out',
          sidebarOpen ? 'translate-x-0' : '-translate-x-full',
        )}
      >
        <button
          onClick={() => setSidebarOpen(false)}
          className="lg:hidden absolute top-2 right-2 w-8 h-8 grid place-items-center rounded-lg hover:bg-slate-100 text-slate-500"
          aria-label="Close menu"
        >
          <X size={18} />
        </button>

        <nav className="flex-1 overflow-y-auto p-3 gap-1 flex flex-col">
          {visibleNav.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/admin'}
              onClick={() => {
                if (window.innerWidth < 1024) setSidebarOpen(false);
              }}
              className={({ isActive }) =>
                cn(
                  'flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition',
                  isActive
                    ? 'bg-brand-50 text-brand-700'
                    : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900',
                )
              }
            >
              <item.icon size={18} />
              {t(item.i18n)}
            </NavLink>
          ))}
        </nav>

        <div className="border-t border-slate-200 p-3">
          <CompactLangSwitcher />
        </div>
      </aside>

      {/* Main content — shifts right by sidebar width on lg+ when open */}
      <main
        className={cn(
          'min-w-0 p-4 sm:p-6 transition-[margin] duration-200',
          sidebarOpen ? 'lg:ml-64' : 'lg:ml-0',
        )}
      >
        <Outlet />
      </main>
    </div>
  );
}
