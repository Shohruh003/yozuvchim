import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Copy, Check, X, ShieldCheck, AlertTriangle } from 'lucide-react';
import toast from 'react-hot-toast';

interface Props {
  open: boolean;
  username: string;
  password: string;
  onClose: () => void;
}

/**
 * Shows the admin login + plaintext password ONCE after promotion / reset.
 * The plaintext password is never stored on the client beyond the lifetime
 * of this modal — closing it loses it forever.
 */
export function CredentialsRevealModal({ open, username, password, onClose }: Props) {
  const { t } = useTranslation();
  const [copied, setCopied] = useState<'user' | 'pass' | 'both' | null>(null);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  if (!open) return null;

  async function copy(text: string, kind: 'user' | 'pass' | 'both') {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(kind);
      toast.success(t('admin.creds.copied'));
      window.setTimeout(() => setCopied(null), 2000);
    } catch {
      toast.error(t('admin.creds.copyFailed'));
    }
  }

  const both = `Login: ${username}\nParol: ${password}\nSayt: https://bot.shohruh.dev/admin/login`;

  return (
    <div
      className="fixed inset-0 z-[80] grid place-items-center p-4 bg-black/60 backdrop-blur-sm animate-fade-in"
      onClick={onClose}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="bg-white w-full max-w-lg rounded-2xl shadow-2xl overflow-hidden"
      >
        <div className="bg-gradient-to-br from-violet-500 to-purple-700 text-white px-6 py-4 flex items-start justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 grid place-items-center rounded-xl bg-white/15">
              <ShieldCheck size={22} />
            </div>
            <div>
              <h3 className="font-bold">{t('admin.creds.title')}</h3>
              <p className="text-xs opacity-80 mt-0.5">{t('admin.creds.subtitle')}</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-white/70 hover:text-white shrink-0"
          >
            <X size={18} />
          </button>
        </div>

        <div className="p-5 space-y-4">
          <div className="flex gap-2 items-start px-3 py-2.5 rounded-xl bg-amber-50 border border-amber-200 text-sm text-amber-800">
            <AlertTriangle size={16} className="shrink-0 mt-0.5" />
            <span>{t('admin.creds.warning')}</span>
          </div>

          <CredField
            label={t('admin.creds.login')}
            value={username}
            onCopy={() => copy(username, 'user')}
            copied={copied === 'user'}
          />
          <CredField
            label={t('admin.creds.password')}
            value={password}
            mono
            onCopy={() => copy(password, 'pass')}
            copied={copied === 'pass'}
          />

          <button
            onClick={() => copy(both, 'both')}
            className="w-full inline-flex items-center justify-center gap-2 px-4 py-3 rounded-xl bg-violet-600 text-white font-semibold hover:bg-violet-700 transition"
          >
            {copied === 'both' ? <Check size={16} /> : <Copy size={16} />}
            {t('admin.creds.copyBoth')}
          </button>

          <button
            onClick={onClose}
            className="w-full px-4 py-2.5 rounded-xl border border-slate-300 text-slate-700 hover:bg-slate-50 font-medium text-sm"
          >
            {t('admin.creds.done')}
          </button>
        </div>
      </div>
    </div>
  );
}

function CredField({
  label,
  value,
  onCopy,
  copied,
  mono,
}: {
  label: string;
  value: string;
  onCopy: () => void;
  copied: boolean;
  mono?: boolean;
}) {
  return (
    <div>
      <label className="text-xs uppercase tracking-wide text-slate-500 font-semibold">
        {label}
      </label>
      <div className="mt-1.5 flex items-center gap-2 px-3 py-2.5 rounded-xl border border-slate-200 bg-slate-50">
        <span
          className={
            'flex-1 select-all break-all ' +
            (mono ? 'font-mono text-slate-900' : 'text-slate-900')
          }
        >
          {value}
        </span>
        <button
          onClick={onCopy}
          className="shrink-0 w-9 h-9 grid place-items-center rounded-lg text-slate-500 hover:bg-slate-200"
          title="Copy"
        >
          {copied ? <Check size={15} className="text-emerald-600" /> : <Copy size={15} />}
        </button>
      </div>
    </div>
  );
}
