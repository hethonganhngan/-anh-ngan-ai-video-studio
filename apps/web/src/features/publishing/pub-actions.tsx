"use client";
import { useState } from "react";
import { BarChart3, Download, ExternalLink, Send, XCircle, CheckCircle2 } from "lucide-react";
import { toast } from "sonner";
import { api, assetUrl, errorMessage } from "@/lib/api";
import { useAction } from "@/hooks/use-mutate";
import { Can } from "@/components/app/require";
import { Field } from "@/components/app/field";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import type { Publication } from "@/types/api";

export function MarkPublished({ pub, open, onOpenChange }: { pub: Publication; open: boolean; onOpenChange: (o: boolean) => void }) {
  const [url, setUrl] = useState("");
  const act = useAction(() => api(`/publications/${pub.id}/mark-published`, { body: { post_url: url } }),
    { success: "Đã ghi nhận bài đăng", invalidate: [["publications"], ["performance"]], onSuccess: () => onOpenChange(false) });
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader><DialogTitle>Đánh dấu đã đăng</DialogTitle><DialogDescription>Nhập URL bài đăng thật trên {pub.platform} (https://…). Hệ thống kiểm tra đúng tên miền nền tảng.</DialogDescription></DialogHeader>
        <Field label="URL bài đăng"><Input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://www.facebook.com/…" data-testid="pub-url" /></Field>
        <DialogFooter><Button variant="outline" onClick={() => onOpenChange(false)}>Huỷ</Button><Button loading={act.isPending} disabled={url.length < 10} onClick={() => act.mutate(undefined)} data-testid="pub-url-submit">Lưu</Button></DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export function SnapshotDialog({ pub, open, onOpenChange }: { pub: Publication; open: boolean; onOpenChange: (o: boolean) => void }) {
  const [f, setF] = useState({ views: "", likes: "0", comments: "0", shares: "0", saves: "0", retention_rate: "", avg_watch_sec: "", conversions: "" });
  const n = (v: string) => (v === "" ? null : Number(v));
  const act = useAction(() => api(`/publications/${pub.id}/snapshots`, { body: {
    views: Number(f.views), likes: Number(f.likes || 0), comments: Number(f.comments || 0), shares: Number(f.shares || 0), saves: Number(f.saves || 0),
    retention_rate: n(f.retention_rate), avg_watch_sec: n(f.avg_watch_sec), conversions: n(f.conversions),
  } }), { success: "Đã lưu số liệu", invalidate: [["performance"], ["publications"]], onSuccess: () => onOpenChange(false) });
  const fields: [keyof typeof f, string][] = [["views", "Lượt xem"], ["likes", "Lượt thích"], ["comments", "Bình luận"], ["shares", "Chia sẻ"], ["saves", "Lưu"],
    ["retention_rate", "Tỷ lệ giữ chân (%) nếu có"], ["avg_watch_sec", "Thời gian xem TB (giây)"], ["conversions", "Chuyển đổi nếu có"]];
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader><DialogTitle>Nhập số liệu sau đăng</DialogTitle><DialogDescription>Số liệu tích luỹ tại thời điểm nhập (lượt xem không được giảm so với lần trước).</DialogDescription></DialogHeader>
        <div className="grid gap-3 md:grid-cols-2">
          {fields.map(([k, l]) => <Field key={k} label={l}><Input type="number" min={0} value={f[k]} onChange={(e) => setF({ ...f, [k]: e.target.value })} data-testid={`snap-${k}`} /></Field>)}
        </div>
        <DialogFooter><Button variant="outline" onClick={() => onOpenChange(false)}>Huỷ</Button><Button loading={act.isPending} disabled={f.views === ""} onClick={() => act.mutate(undefined)} data-testid="snap-submit">Lưu số liệu</Button></DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export function PubRowActions({ pub, onChange }: { pub: Publication; onChange: () => void }) {
  const [mark, setMark] = useState(false);
  const [snap, setSnap] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const exportPkg = useAction(() => api<{ asset_id: string }>(`/publications/${pub.id}/export`, { method: "POST" }),
    { success: "Đã xuất gói đăng (ZIP)", invalidate: [["publications"]], onSuccess: onChange });
  const cancel = useAction(() => api(`/publications/${pub.id}/cancel`, { method: "POST" }), { success: "Đã huỷ bài đăng", invalidate: [["publications"]] });
  const viaApi = async () => {
    setBusy("api");
    try { await api(`/publications/${pub.id}/publish-api`, { method: "POST" }); toast.success("Đã đăng qua API"); onChange(); }
    catch (e) { toast.error(errorMessage(e), { id: "publish-api-error" }); }
    finally { setBusy(null); }
  };
  const done = pub.status === "PUBLISHED";
  return (
    <div className="flex flex-wrap justify-end gap-1">
      {pub.export_asset_id && <Button size="sm" variant="ghost" asChild><a href={assetUrl(pub.export_asset_id, true)} data-testid="pub-download"><Download />ZIP</a></Button>}
      {!done && pub.status !== "CANCELLED" && (<>
        <Can perm="publish.manage"><Button size="sm" variant="ghost" onClick={() => exportPkg.mutate(undefined)} loading={exportPkg.isPending} data-testid="pub-export"><Download />Xuất file</Button></Can>
        <Can perm="publish.execute">
          <Button size="sm" variant="ghost" onClick={() => setMark(true)} data-testid="pub-mark"><CheckCircle2 />Đã đăng</Button>
          <Button size="sm" variant="ghost" onClick={viaApi} loading={busy === "api"} data-testid="pub-api"><Send />Đăng qua API</Button>
        </Can>
        <Can perm="publish.manage"><Button size="sm" variant="ghost" onClick={() => cancel.mutate(undefined)} data-testid="pub-cancel"><XCircle />Huỷ</Button></Can>
      </>)}
      {done && pub.post_url && <Button size="sm" variant="ghost" asChild><a href={pub.post_url} target="_blank" rel="noreferrer noopener"><ExternalLink />Xem</a></Button>}
      {done && <Can perm="analytics.enter"><Button size="sm" variant="ghost" onClick={() => setSnap(true)} data-testid="pub-snapshot"><BarChart3 />Nhập số liệu</Button></Can>}
      <MarkPublished pub={pub} open={mark} onOpenChange={setMark} />
      <SnapshotDialog pub={pub} open={snap} onOpenChange={setSnap} />
    </div>
  );
}
