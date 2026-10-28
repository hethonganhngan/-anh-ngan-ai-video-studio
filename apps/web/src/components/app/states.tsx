"use client";
import { AlertTriangle, Inbox, Lock, RefreshCw } from "lucide-react";
import type { ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/misc";
import { errorMessage } from "@/lib/api";

export function LoadingState({ rows = 3, label = "Đang tải dữ liệu…" }: { rows?: number; label?: string }) {
  return (
    <div className="space-y-3" role="status" aria-live="polite" data-testid="state-loading">
      <span className="sr-only">{label}</span>
      {Array.from({ length: rows }).map((_, i) => <Skeleton key={i} className="h-14 w-full" />)}
    </div>
  );
}

export function EmptyState({ title = "Chưa có dữ liệu", description, action }: { title?: string; description?: string; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-slate-300 bg-white px-6 py-12 text-center" data-testid="state-empty">
      <Inbox className="mb-3 h-10 w-10 text-slate-400" />
      <p className="font-medium text-slate-800">{title}</p>
      {description && <p className="mt-1 max-w-md text-sm text-slate-500">{description}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  return (
    <div className="flex items-start gap-3 rounded-xl border border-red-200 bg-red-50 p-4 text-red-800" role="alert" data-testid="state-error">
      <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0" />
      <div className="flex-1">
        <p className="font-medium">Không tải được dữ liệu</p>
        <p className="text-sm">{errorMessage(error)}</p>
      </div>
      {onRetry && <Button size="sm" variant="outline" onClick={onRetry}><RefreshCw />Thử lại</Button>}
    </div>
  );
}

export function AccessDenied({ perm }: { perm?: string }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border border-amber-200 bg-amber-50 px-6 py-12 text-center" data-testid="state-denied">
      <Lock className="mb-3 h-10 w-10 text-amber-600" />
      <p className="font-medium text-amber-900">Bạn không có quyền truy cập màn hình này</p>
      {perm && <p className="mt-1 text-sm text-amber-800">Quyền cần có: <code>{perm}</code>. Liên hệ quản trị hệ thống.</p>}
    </div>
  );
}

/** Bọc truy vấn: tự hiển thị loading / error / empty. */
export function QueryView<T>({ q, empty, isEmpty, children, rows }: {
  q: { isLoading: boolean; error: unknown; data: T | undefined; refetch: () => unknown };
  empty?: ReactNode; isEmpty?: (d: T) => boolean; children: (d: T) => ReactNode; rows?: number;
}) {
  if (q.isLoading) return <LoadingState rows={rows} />;
  if (q.error) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  if (q.data === undefined) return <LoadingState rows={rows} />;
  if (isEmpty && isEmpty(q.data)) return <>{empty ?? <EmptyState />}</>;
  return <>{children(q.data)}</>;
}
