import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Lock, User as UserIcon, ShieldCheck, Eye, EyeOff } from 'lucide-react';
import toast from 'react-hot-toast';

import { apiPost } from '@/lib/api';
import { useAuthStore } from '@/stores/auth';

export default function AdminLoginPage() {
  const navigate = useNavigate();
  const setToken = useAuthStore((s) => s.setAccessToken);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [show, setShow] = useState(false);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!username || !password) {
      toast.error('Login va parol kiriting');
      return;
    }
    setBusy(true);
    try {
      const r = await apiPost<{ access_token: string }>('/auth/admin/login', {
        username,
        password,
      });
      setToken(r.access_token);
      toast.success('Xush kelibsiz');
      navigate('/admin', { replace: true });
    } catch (e: any) {
      const msg = e?.response?.data?.message;
      toast.error(msg || 'Login yoki parol noto\'g\'ri');
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-h-screen grid place-items-center px-4 bg-gradient-to-br from-slate-900 via-slate-800 to-indigo-900">
      <form
        onSubmit={submit}
        className="w-full max-w-md bg-white rounded-2xl shadow-2xl p-7 sm:p-8"
      >
        <div className="flex items-center gap-3 mb-6">
          <div className="w-12 h-12 grid place-items-center rounded-2xl bg-gradient-to-br from-violet-500 to-purple-700 text-white">
            <ShieldCheck size={22} />
          </div>
          <div>
            <h1 className="text-xl font-bold text-slate-900">Admin panel</h1>
            <p className="text-xs text-slate-500">Yozuvchim — boshqaruv</p>
          </div>
        </div>

        <div className="space-y-3">
          <Field icon={<UserIcon size={16} />}>
            <input
              type="text"
              autoComplete="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="Login"
              className="w-full bg-transparent outline-none text-slate-900 placeholder:text-slate-400"
              autoFocus
            />
          </Field>

          <Field icon={<Lock size={16} />}>
            <input
              type={show ? 'text' : 'password'}
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Parol"
              className="w-full bg-transparent outline-none text-slate-900 placeholder:text-slate-400"
            />
            <button
              type="button"
              onClick={() => setShow((s) => !s)}
              className="text-slate-400 hover:text-slate-600 shrink-0"
            >
              {show ? <EyeOff size={16} /> : <Eye size={16} />}
            </button>
          </Field>
        </div>

        <button
          type="submit"
          disabled={busy}
          className="mt-5 w-full px-5 py-3 rounded-xl bg-gradient-to-br from-violet-500 to-purple-700 text-white font-semibold hover:opacity-95 disabled:opacity-50 transition"
        >
          {busy ? 'Kirilmoqda...' : 'Kirish'}
        </button>

        <p className="mt-4 text-xs text-slate-400 text-center">
          Faqat ruxsat etilgan adminlar uchun.
        </p>
      </form>
    </div>
  );
}

function Field({ icon, children }: { icon: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="flex items-center gap-3 px-4 py-3 rounded-xl border border-slate-200 bg-slate-50 focus-within:border-brand-400 focus-within:bg-white transition">
      <span className="text-slate-400">{icon}</span>
      {children}
    </div>
  );
}
