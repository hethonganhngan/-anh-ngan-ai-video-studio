"use client";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { Facebook, Link2, Unlink } from "lucide-react";
import { api, errorMessage } from "@/lib/api";
import { useAction } from "@/hooks/use-mutate";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input, NativeSelect } from "@/components/ui/input";
import { formatDate } from "@/lib/utils";

export type FbTarget = { page_id: string; page_name: string; mode: string; connected_at: string };
type Page = { id: string; name: string; can_post: boolean };

/** M13: gắn Fanpage cho kênh. Video đã duyệt của kênh tự lên Fanpage dạng BẢN NHÁP chờ duyệt (không tự công khai). */
export function FacebookConnect({ channelId, target, canEdit }: { channelId: string; target?: FbTarget; canEdit: boolean }) {
  const [open, setOpen] = useState(false);
  const [pageId, setPageId] = useState("");
  const pages = useQuery<Page[]>({ queryKey: ["fb-pages"], queryFn: () => api("/channels/facebook/pages"), enabled: open, retry: false });
  const save = useAction((pid: string | null) => api(`/channels/${channelId}/facebook`, { method: "PUT", body: { page_id: pid } }),
    { success: (r) => ((r as { publish_targets?: { FACEBOOK?: FbTarget } }).publish_targets?.FACEBOOK ? "Đã gắn Fanpage cho kênh" : "Đã bỏ gắn Fanpage"),
      invalidate: [["channels-full"]], onSuccess: () => setOpen(false) });
  return (
    <div className="rounded-lg border border-slate-200 p-3" data-testid="fb-connect">
      <div className="flex flex-wrap items-center gap-2">
        <Facebook className="h-4 w-4 text-[#1877F2]" />
        <p className="text-sm font-medium">Fanpage Facebook</p>
        {target ? (
          <>
            <Badge variant="green" data-testid="fb-connected">{target.page_name || target.page_id}</Badge>
            <Badge variant="orange">Chỉ đăng bản nháp chờ duyệt</Badge>
            <span className="text-xs text-slate-500">gắn {formatDate(target.connected_at)}</span>
          </>
        ) : <Badge variant="gray">Chưa gắn</Badge>}
        {canEdit && (
          <div className="ml-auto flex gap-1">
            <Button size="sm" variant="outline" onClick={() => setOpen((o) => !o)} data-testid="fb-connect-open"><Link2 />{target ? "Đổi Fanpage" : "Kết nối Facebook"}</Button>
            {target && <Button size="sm" variant="ghost" loading={save.isPending} onClick={() => save.mutate(null)} data-testid="fb-disconnect"><Unlink />Bỏ gắn</Button>}
          </div>
        )}
      </div>
      <p className="mt-1 text-xs text-slate-500">Video được duyệt ở M07 sẽ tự tải lên Fanpage dưới dạng <b>bản nháp</b>. Bài chỉ công khai khi anh/chị bấm đăng trong Meta Business Suite.</p>
      {open && (
        <div className="mt-2 space-y-2 rounded-lg bg-slate-50 p-2">
          {pages.isLoading && <p className="text-xs text-slate-500">Đang đọc danh sách Fanpage…</p>}
          {pages.isError && (
            <p className="text-xs text-red-700" role="alert">{errorMessage(pages.error)} — nhập token Facebook tại <Link className="underline" href="/settings">M15 → Kết nối API → Facebook Pages</Link>, bấm Kiểm tra rồi quay lại.</p>
          )}
          {pages.data && (
            <div className="flex flex-wrap gap-2">
              <NativeSelect className="w-72" value={pageId} onChange={(e) => setPageId(e.target.value)} data-testid="fb-page-select">
                <option value="">— Chọn Fanpage —</option>
                {pages.data.map((p) => <option key={p.id} value={p.id} disabled={!p.can_post}>{p.name} ({p.id}){!p.can_post && " — thiếu quyền tạo nội dung"}</option>)}
              </NativeSelect>
              <Button size="sm" disabled={!pageId} loading={save.isPending} onClick={() => save.mutate(pageId)} data-testid="fb-page-save">Gắn vào kênh</Button>
            </div>
          )}
          {pages.isError && (
            <div className="flex flex-wrap gap-2">
              <Input className="w-72" placeholder="Hoặc nhập Page ID (dãy số)" value={pageId} onChange={(e) => setPageId(e.target.value.trim())} data-testid="fb-page-id" />
              <Button size="sm" disabled={!/^\d{5,30}$/.test(pageId)} loading={save.isPending} onClick={() => save.mutate(pageId)}>Gắn</Button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
