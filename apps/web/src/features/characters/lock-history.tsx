"use client";
import { Badge, type BadgeVariant } from "@/components/ui/badge";
import { formatDate } from "@/lib/utils";
import type { Lock } from "@/types/api";

export const LOCK_STATUS: Record<string, { label: string; variant: BadgeVariant }> = {
  DRAFT: { label: "Nháp — chờ duyệt", variant: "yellow" },
  APPROVED: { label: "Đang hiệu lực", variant: "green" },
  RETIRED: { label: "Đã thay thế", variant: "gray" },
};

export function LockHistory({ locks, activeId, onApprove, canApprove, testid }: {
  locks: Lock[]; activeId: string | null; onApprove: (id: string) => void; canApprove: boolean; testid: string;
}) {
  if (!locks.length) return <p className="text-sm text-slate-500">Chưa có bản khoá nào.</p>;
  return (
    <div className="space-y-2" data-testid={testid}>
      {locks.map((l) => (
        <div key={l.id} className="rounded-lg border border-slate-200 p-3 text-sm" data-testid="lock-row" data-lock-status={l.status}>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="font-medium">Phiên bản v{l.version_no} {l.id === activeId && <Badge variant="navy">Active</Badge>}</p>
            <div className="flex items-center gap-2">
              <Badge variant={LOCK_STATUS[l.status]?.variant ?? "gray"}>{LOCK_STATUS[l.status]?.label ?? l.status}</Badge>
              {l.status === "DRAFT" && canApprove && (
                <button className="rounded-md bg-emerald-600 px-3 py-1 text-xs font-medium text-white hover:bg-emerald-700" onClick={() => onApprove(l.id)} data-testid="approve-lock">Duyệt khoá</button>
              )}
            </div>
          </div>
          <p className="text-xs text-slate-500">Tạo {formatDate(l.created_at)}{l.approved_at ? ` · Duyệt ${formatDate(l.approved_at)}` : ""}{l.retired_at ? ` · Thay thế ${formatDate(l.retired_at)}` : ""}{l.change_note ? ` · ${l.change_note}` : ""}</p>
          <details className="mt-1 text-xs"><summary className="cursor-pointer text-brand-700">Dữ liệu khoá (bất biến sau khi duyệt)</summary>
            <pre className="mt-1 max-h-60 overflow-auto rounded bg-slate-50 p-2">{JSON.stringify(l.lock_data, null, 2)}</pre>
          </details>
        </div>
      ))}
    </div>
  );
}
