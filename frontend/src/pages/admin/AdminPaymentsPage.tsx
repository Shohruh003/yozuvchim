import { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import toast from 'react-hot-toast';
import { Check, X as Reject, Image as ImgIcon, ZoomIn } from 'lucide-react';

import { api, apiGet, apiPost } from '@/lib/api';
import { formatNumber } from '@/lib/utils';
import { ConfirmDialog } from '@/components/admin/ConfirmDialog';
import { ApproveAmountModal } from '@/components/admin/ApproveAmountModal';

interface PendingPayment {
  id: number;
  user_id: string;
  username: string;
  full_name: string;
  amount: number;
  status: string;
  screenshot_file_id?: string;
  created_at: string;
}

interface PendingResp {
  total: number;
  items: PendingPayment[];
}

const PAGE_SIZE = 20;

export default function AdminPaymentsPage() {
  const { t, i18n } = useTranslation();
  const [data, setData] = useState<PendingResp | null>(null);
  const [page, setPage] = useState(0);
  const [busy, setBusy] = useState<number | null>(null);
  const [preview, setPreview] = useState<{ id: number; url: string } | null>(null);
  const [rejectTarget, setRejectTarget] = useState<PendingPayment | null>(null);
  const [approveTarget, setApproveTarget] = useState<PendingPayment | null>(null);

  function reload() {
    apiGet<PendingResp>(
      `/admin/payments/pending?limit=${PAGE_SIZE}&offset=${page * PAGE_SIZE}`,
    )
      .then(setData)
      .catch(() => null);
  }

  useEffect(() => {
    reload();
    window.scrollTo({ top: 0, behavior: 'smooth' });
    const id = window.setInterval(reload, 20_000);
    return () => window.clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page]);

  const items = data?.items ?? null;
  const total = data?.total ?? 0;
  const totalPages = useMemo(
    () => Math.max(1, Math.ceil(total / PAGE_SIZE)),
    [total],
  );

  async function performApprove(amount: number) {
    if (!approveTarget) return;
    const p = approveTarget;
    setBusy(p.id);
    try {
      await apiPost(`/admin/payments/${p.id}/approve`, { amount });
      toast.success(t('admin.pay.approved'));
      reload();
      setApproveTarget(null);
    } catch (e: any) {
      toast.error(e?.response?.data?.message || 'Xato');
    } finally {
      setBusy(null);
    }
  }

  async function performReject() {
    if (!rejectTarget) return;
    const p = rejectTarget;
    setBusy(p.id);
    try {
      await apiPost(`/admin/payments/${p.id}/reject`, {});
      toast.success(t('admin.pay.rejected'));
      reload();
      setRejectTarget(null);
    } catch (e: any) {
      toast.error(e?.response?.data?.message || 'Xato');
    } finally {
      setBusy(null);
    }
  }

  function closePreview() {
    // Don't revoke — the URL is cached/owned by the inline <ScreenshotImage>.
    setPreview(null);
  }

  const fmtDate = (s: string) => {
    const d = new Date(s);
    const pad = (n: number) => String(n).padStart(2, '0');
    return {
      date: `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`,
      time: `${pad(d.getHours())}:${pad(d.getMinutes())}`,
    };
  };

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl sm:text-2xl font-bold text-slate-900">{t('admin.pay.title')}</h1>
        <p className="text-sm text-slate-500 mt-0.5">{t('admin.pay.subtitle')}</p>
      </div>

      {items === null ? (
        <div className="text-slate-400 text-sm">{t('common.loading')}</div>
      ) : items.length === 0 ? (
        <div className="bg-white rounded-2xl border border-slate-200 p-10 text-center text-slate-400">
          {t('admin.pay.empty')}
        </div>
      ) : (
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3 sm:gap-4">
          {items.map((p) => (
            <article
              key={p.id}
              className="bg-white rounded-2xl border border-slate-200 overflow-hidden flex flex-col"
            >
              <ScreenshotImage
                paymentId={p.id}
                onZoom={(url) => setPreview({ id: p.id, url })}
              />
              <div className="p-4 flex-1 flex flex-col">
                <div className="flex items-start justify-between gap-2 mb-2">
                  <div className="min-w-0">
                    <div className="font-semibold text-slate-900 truncate">
                      {p.full_name || p.username || `#${p.user_id}`}
                    </div>
                    <div className="text-xs text-slate-500 truncate">
                      {p.username ? `@${p.username}` : `#${p.user_id}`}
                    </div>
                  </div>
                  {/* Skrinshotgacha summa noma'lum — adminga "Tasdiqlash"da kiritadi */}
                  {p.amount > 0 && (
                    <div className="text-right shrink-0">
                      <div className="font-bold text-slate-900 tabular-nums">
                        {formatNumber(p.amount)}
                      </div>
                      <div className="text-[10px] text-slate-500">so'm</div>
                    </div>
                  )}
                </div>
                {(() => {
                  const dt = fmtDate(p.created_at);
                  return (
                    <div className="text-[11px] text-slate-500 mt-1 space-y-0.5">
                      <div>sana: <span className="font-medium text-slate-700 tabular-nums">{dt.date}</span></div>
                      <div>vaqt: <span className="font-medium text-slate-700 tabular-nums">{dt.time}</span></div>
                    </div>
                  );
                })()}

                <div className="mt-auto pt-4 flex gap-2">
                  <button
                    disabled={busy === p.id}
                    onClick={() => setApproveTarget(p)}
                    className="flex-1 inline-flex items-center justify-center gap-1.5 px-3 py-2 rounded-xl bg-emerald-500 text-white font-medium text-sm hover:bg-emerald-600 disabled:opacity-50"
                  >
                    <Check size={15} /> {t('admin.pay.approve')}
                  </button>
                  <button
                    disabled={busy === p.id}
                    onClick={() => setRejectTarget(p)}
                    className="flex-1 inline-flex items-center justify-center gap-1.5 px-3 py-2 rounded-xl border border-rose-300 text-rose-700 bg-rose-50 hover:bg-rose-100 font-medium text-sm disabled:opacity-50"
                  >
                    <Reject size={15} /> {t('admin.pay.reject')}
                  </button>
                </div>
              </div>
            </article>
          ))}
        </div>
      )}

      {data && total > PAGE_SIZE && (
        <div className="flex items-center justify-between text-sm">
          <div className="text-slate-500">
            {t('admin.users.pageOf', { current: page + 1, total: totalPages })}
          </div>
          <div className="flex gap-2">
            <button
              disabled={page === 0}
              onClick={() => setPage((p) => Math.max(0, p - 1))}
              className="px-3 py-1.5 rounded-lg border border-slate-300 disabled:opacity-40 hover:bg-slate-50 bg-white"
            >
              ←
            </button>
            <button
              disabled={page + 1 >= totalPages}
              onClick={() => setPage((p) => p + 1)}
              className="px-3 py-1.5 rounded-lg border border-slate-300 disabled:opacity-40 hover:bg-slate-50 bg-white"
            >
              →
            </button>
          </div>
        </div>
      )}

      <ApproveAmountModal
        open={!!approveTarget}
        userName={
          approveTarget
            ? approveTarget.full_name ||
              approveTarget.username ||
              `#${approveTarget.user_id}`
            : ''
        }
        initialAmount={approveTarget?.amount}
        busy={busy === approveTarget?.id}
        onCancel={() => setApproveTarget(null)}
        onConfirm={performApprove}
      />

      <ConfirmDialog
        open={!!rejectTarget}
        title={t('admin.pay.reject')}
        message={t('admin.pay.confirmReject')}
        confirmLabel={t('admin.pay.reject')}
        cancelLabel={t('admin.cards.cancel')}
        tone="danger"
        onCancel={() => setRejectTarget(null)}
        onConfirm={performReject}
      />

      {preview && (
        <div
          className="fixed inset-0 z-[70] bg-black/80 grid place-items-center p-4 animate-fade-in"
          onClick={closePreview}
        >
          <img
            src={preview.url}
            alt="Screenshot"
            className="max-h-full max-w-full rounded-2xl shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          />
          <button
            onClick={closePreview}
            className="absolute top-4 right-4 w-10 h-10 grid place-items-center rounded-full bg-white/10 text-white hover:bg-white/20"
          >
            <Reject size={20} />
          </button>
        </div>
      )}
    </div>
  );
}

/**
 * Loads a payment screenshot via authenticated request and shows it inline.
 * Click on the image opens the full-size lightbox via `onZoom`.
 */
function ScreenshotImage({
  paymentId,
  onZoom,
}: {
  paymentId: number;
  onZoom: (url: string) => void;
}) {
  const [url, setUrl] = useState<string | null>(null);
  const [state, setState] = useState<'loading' | 'ready' | 'error'>('loading');

  useEffect(() => {
    let cancelled = false;
    let blobUrl: string | null = null;

    api
      .get(`/admin/payments/${paymentId}/screenshot`, { responseType: 'blob' })
      .then((res) => {
        if (cancelled) return;
        blobUrl = URL.createObjectURL(new Blob([res.data]));
        setUrl(blobUrl);
        setState('ready');
      })
      .catch(() => {
        if (cancelled) return;
        setState('error');
      });

    return () => {
      cancelled = true;
      if (blobUrl) URL.revokeObjectURL(blobUrl);
    };
  }, [paymentId]);

  if (state === 'loading') {
    return (
      <div className="aspect-video bg-slate-100 grid place-items-center text-slate-400">
        <span className="w-6 h-6 border-2 border-slate-300 border-t-brand-500 rounded-full animate-spin" />
      </div>
    );
  }
  if (state === 'error' || !url) {
    return (
      <div className="aspect-video bg-slate-100 grid place-items-center text-slate-400 text-xs">
        <ImgIcon size={28} className="opacity-50 mb-1" />
        Screenshot mavjud emas
      </div>
    );
  }

  return (
    <button
      onClick={() => onZoom(url)}
      className="aspect-video bg-slate-100 relative overflow-hidden group"
      title="Kattalashtirish"
    >
      <img
        src={url}
        alt="Payment screenshot"
        className="w-full h-full object-cover transition group-hover:scale-105"
      />
      <span className="absolute top-2 right-2 w-8 h-8 grid place-items-center rounded-full bg-black/40 text-white opacity-0 group-hover:opacity-100 transition">
        <ZoomIn size={14} />
      </span>
    </button>
  );
}
