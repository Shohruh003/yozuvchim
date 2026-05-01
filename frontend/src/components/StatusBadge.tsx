import { useTranslation } from 'react-i18next';
import { cn } from '@/lib/utils';

const COLORS: Record<string, string> = {
  done: 'bg-emerald-100 text-emerald-700 border-emerald-200',
  processing: 'bg-amber-100 text-amber-700 border-amber-200',
  queued: 'bg-blue-100 text-blue-700 border-blue-200',
  error: 'bg-rose-100 text-rose-700 border-rose-200',
  cancelled: 'bg-slate-100 text-slate-600 border-slate-200',
};

export function StatusBadge({ status }: { status: string }) {
  const { t } = useTranslation();
  return (
    <span
      className={cn(
        'px-2.5 py-1 rounded-lg text-xs font-medium border',
        COLORS[status] ?? 'bg-slate-100 text-slate-700 border-slate-200',
      )}
    >
      {t(`status.${status}`, { defaultValue: status })}
    </span>
  );
}
