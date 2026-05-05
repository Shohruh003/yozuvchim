import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import toast from 'react-hot-toast';
import { Lock, User as UserIcon, Eye, EyeOff, Save, ShieldCheck } from 'lucide-react';

import { apiGet, apiPost } from '@/lib/api';

interface MeResp {
  role: string;
}

export default function AdminSettingsPage() {
  const { t } = useTranslation();
  const [me, setMe] = useState<MeResp | null>(null);
  const [currentUsername, setCurrentUsername] = useState('');

  useEffect(() => {
    apiGet<MeResp>('/users/me').then(setMe).catch(() => null);
  }, []);

  useEffect(() => {
    if (me?.role !== 'superadmin') return;
    apiGet<{ username: string }>('/auth/admin/credentials')
      .then((r) => setCurrentUsername(r.username))
      .catch(() => null);
  }, [me]);

  if (!me) {
    return <div className="text-slate-400 text-sm">{t('common.loading')}</div>;
  }
  if (me.role !== 'superadmin') {
    return (
      <div className="bg-amber-50 border border-amber-200 text-amber-800 rounded-2xl p-6">
        {t('admin.settings.superadminOnly')}
      </div>
    );
  }

  return (
    <div className="space-y-4 max-w-2xl">
      <div>
        <h1 className="text-xl sm:text-2xl font-bold text-slate-900">
          {t('admin.settings.title')}
        </h1>
        <p className="text-sm text-slate-500 mt-0.5">{t('admin.settings.subtitle')}</p>
      </div>

      <CredentialsCard
        currentUsername={currentUsername}
        onUpdated={(u) => setCurrentUsername(u)}
      />
    </div>
  );
}

function CredentialsCard({
  currentUsername,
  onUpdated,
}: {
  currentUsername: string;
  onUpdated: (username: string) => void;
}) {
  const { t } = useTranslation();
  const [newUsername, setNewUsername] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [currentPassword, setCurrentPassword] = useState('');
  const [showCur, setShowCur] = useState(false);
  const [showNew, setShowNew] = useState(false);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!currentPassword) {
      toast.error(t('admin.settings.currentPasswordRequired'));
      return;
    }
    if (newPassword && newPassword.length < 8) {
      toast.error(t('admin.settings.passwordTooShort'));
      return;
    }
    if (newPassword && newPassword !== confirmPassword) {
      toast.error(t('admin.settings.passwordsDontMatch'));
      return;
    }
    if (!newUsername.trim() && !newPassword) {
      toast.error(t('admin.settings.nothingToUpdate'));
      return;
    }

    setBusy(true);
    try {
      const r = await apiPost<{ username: string }>('/auth/admin/credentials', {
        current_password: currentPassword,
        new_username: newUsername.trim() || undefined,
        new_password: newPassword || undefined,
      });
      toast.success(t('admin.settings.updated'));
      onUpdated(r.username);
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
      setNewUsername('');
    } catch (e: any) {
      toast.error(e?.response?.data?.message || t('admin.settings.error'));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form
      onSubmit={submit}
      className="bg-white rounded-2xl border border-slate-200 p-5 sm:p-6 space-y-4"
    >
      <div className="flex items-center gap-3 mb-2">
        <div className="w-10 h-10 grid place-items-center rounded-xl bg-violet-100 text-violet-600">
          <ShieldCheck size={18} />
        </div>
        <div>
          <h3 className="font-semibold text-slate-900">{t('admin.settings.credsTitle')}</h3>
          <p className="text-xs text-slate-500 mt-0.5">
            {t('admin.settings.currentLogin')}: <span className="font-medium text-slate-700">{currentUsername}</span>
          </p>
        </div>
      </div>

      <Field label={t('admin.settings.newUsername')} hint={t('admin.settings.optionalHint')}>
        <div className="flex items-center gap-3 px-4 py-2.5 rounded-xl border border-slate-300 bg-white">
          <UserIcon size={16} className="text-slate-400" />
          <input
            type="text"
            value={newUsername}
            onChange={(e) => setNewUsername(e.target.value)}
            placeholder={currentUsername}
            autoComplete="username"
            className="flex-1 bg-transparent outline-none text-slate-900"
          />
        </div>
      </Field>

      <Field label={t('admin.settings.newPassword')} hint={t('admin.settings.optionalHint')}>
        <div className="flex items-center gap-3 px-4 py-2.5 rounded-xl border border-slate-300 bg-white">
          <Lock size={16} className="text-slate-400" />
          <input
            type={showNew ? 'text' : 'password'}
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            placeholder={t('admin.settings.passwordPlaceholder')}
            autoComplete="new-password"
            className="flex-1 bg-transparent outline-none text-slate-900"
          />
          <button
            type="button"
            onClick={() => setShowNew((s) => !s)}
            className="text-slate-400 hover:text-slate-600 shrink-0"
          >
            {showNew ? <EyeOff size={16} /> : <Eye size={16} />}
          </button>
        </div>
      </Field>

      {newPassword && (
        <Field label={t('admin.settings.confirmPassword')}>
          <div className="flex items-center gap-3 px-4 py-2.5 rounded-xl border border-slate-300 bg-white">
            <Lock size={16} className="text-slate-400" />
            <input
              type={showNew ? 'text' : 'password'}
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              autoComplete="new-password"
              className="flex-1 bg-transparent outline-none text-slate-900"
            />
          </div>
        </Field>
      )}

      <div className="border-t border-slate-200 pt-4">
        <Field label={t('admin.settings.currentPassword')} hint={t('admin.settings.requiredHint')}>
          <div className="flex items-center gap-3 px-4 py-2.5 rounded-xl border border-slate-300 bg-white">
            <Lock size={16} className="text-slate-400" />
            <input
              type={showCur ? 'text' : 'password'}
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              autoComplete="current-password"
              className="flex-1 bg-transparent outline-none text-slate-900"
              required
            />
            <button
              type="button"
              onClick={() => setShowCur((s) => !s)}
              className="text-slate-400 hover:text-slate-600 shrink-0"
            >
              {showCur ? <EyeOff size={16} /> : <Eye size={16} />}
            </button>
          </div>
        </Field>
      </div>

      <button
        type="submit"
        disabled={busy}
        className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-violet-600 text-white font-semibold hover:bg-violet-700 disabled:opacity-50 transition"
      >
        <Save size={15} />
        {busy ? t('admin.settings.saving') : t('admin.settings.save')}
      </button>
    </form>
  );
}

function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <label className="block text-sm font-medium text-slate-700 mb-1.5">
        {label}{' '}
        {hint && <span className="text-xs text-slate-400 font-normal">({hint})</span>}
      </label>
      {children}
    </div>
  );
}
