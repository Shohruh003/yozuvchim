import { ReactNode, useEffect, useState } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { apiGet } from '@/lib/api';
import { useAuthStore } from '@/stores/auth';

interface Me {
  id: string;
  role: string;
}

export function AdminGuard({ children }: { children: ReactNode }) {
  const token = useAuthStore((s) => s.accessToken);
  const location = useLocation();
  const [state, setState] = useState<'loading' | 'allow' | 'deny'>('loading');

  useEffect(() => {
    if (!token) {
      setState('deny');
      return;
    }
    apiGet<Me>('/users/me')
      .then((u) => setState(u.role === 'admin' || u.role === 'superadmin' ? 'allow' : 'deny'))
      .catch(() => setState('deny'));
  }, [token]);

  if (!token) {
    return <Navigate to="/admin/login" replace />;
  }
  if (state === 'loading') {
    return (
      <div className="min-h-screen grid place-items-center text-slate-400 text-sm">
        Yuklanmoqda...
      </div>
    );
  }
  if (state === 'deny') {
    // Token exists but user is not an admin — clear it so the login form
    // doesn't get stuck behind a non-admin session.
    useAuthStore.getState().clear();
    const redirect = encodeURIComponent(location.pathname + location.search);
    return <Navigate to={`/admin/login?redirect=${redirect}`} replace />;
  }
  return <>{children}</>;
}
