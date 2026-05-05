import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

import { apiPost } from '@/lib/api';
import { useAuthStore } from '@/stores/auth';

export default function LoginPage() {
  const navigate = useNavigate();
  const setToken = useAuthStore((s) => s.setAccessToken);
  const [params] = useSearchParams();
  const { t } = useTranslation();
  const [status, setStatus] = useState<{ key: string; tone: 'info' | 'error' | 'success' }>(
    { key: 'login.loading', tone: 'info' },
  );

  useEffect(() => {
    let cancelled = false;
    // Where to send the user after a successful login.
    const rawRedirect = params.get('redirect') || '';
    const target =
      rawRedirect && rawRedirect.startsWith('/') && !rawRedirect.startsWith('//')
        ? rawRedirect
        : '/profile';

    async function attempt() {
      const tg = (window as any).Telegram?.WebApp;
      const externalToken = params.get('token');

      if (tg) {
        try {
          tg.ready?.();
          tg.expand?.();
        } catch {
          /* noop */
        }
        let initData: string = tg.initData || '';
        for (let i = 0; i < 30 && !initData; i++) {
          await new Promise((r) => setTimeout(r, 100));
          initData = (window as any).Telegram?.WebApp?.initData || '';
        }
        if (initData) {
          try {
            const r = await apiPost<{ access_token: string }>('/auth/telegram/webapp', {
              init_data: initData,
            });
            if (cancelled) return;
            setToken(r.access_token);
            setStatus({ key: 'login.redirecting', tone: 'success' });
            navigate(target, { replace: true });
            return;
          } catch {
            /* fall through */
          }
        }
      }

      if (externalToken) {
        try {
          const r = await apiPost<{ access_token: string }>('/auth/telegram/token', {
            token: externalToken,
          });
          if (cancelled) return;
          setToken(r.access_token);
          setStatus({ key: 'login.redirecting', tone: 'success' });
          navigate(target, { replace: true });
          return;
        } catch {
          setStatus({ key: 'login.tokenInvalid', tone: 'error' });
          return;
        }
      }

      setStatus({ key: 'login.openInTelegram', tone: 'error' });
    }

    attempt();
    return () => {
      cancelled = true;
    };
  }, [navigate, params, setToken]);

  const tone =
    status.tone === 'error'
      ? 'bg-rose-50 text-rose-700 border-rose-200'
      : status.tone === 'success'
        ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
        : 'bg-blue-50 text-blue-700 border-blue-200';

  return (
    <div className="min-h-screen grid place-items-center px-4">
      <div className="w-full max-w-md bg-white rounded-2xl shadow-xl border border-slate-200 p-8 text-center">
        <div className="mx-auto w-16 h-16 grid place-items-center rounded-2xl bg-brand-500 text-white text-2xl font-bold mb-5">
          Y
        </div>
        <h1 className="text-2xl font-bold text-slate-900">Yozuvchim</h1>
        <div className={`mt-6 text-sm rounded-xl p-4 border ${tone} flex items-center gap-3 justify-center`}>
          {status.tone === 'info' && (
            <span className="w-5 h-5 border-4 border-blue-200 border-t-blue-500 rounded-full animate-spin" />
          )}
          <span>{t(status.key)}</span>
        </div>
      </div>
    </div>
  );
}
