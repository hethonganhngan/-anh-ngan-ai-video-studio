"use client";
import { useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, Trash2, Upload } from "lucide-react";
import { toast } from "sonner";
import { api, assetUrl, errorMessage } from "@/lib/api";
import { useAction } from "@/hooks/use-mutate";
import { Can } from "@/components/app/require";
import { ConfirmButton } from "@/components/app/confirm";
import { Field } from "@/components/app/field";
import { AssetImage, VideoPlayer } from "@/components/app/media";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, NativeSelect, Textarea } from "@/components/ui/input";
import { ASSET_TYPES, USAGE_RIGHTS } from "@/lib/labels";
import { formatBytes, formatDate } from "@/lib/utils";
import type { Asset } from "@/types/api";

export function Preview({ a, className }: { a: Asset; className?: string }) {
  const kind = a.mime_type.split("/")[0];
  if (kind === "image") return <AssetImage assetId={a.id} alt={a.name} className={className ?? "aspect-square w-full"} />;
  if (kind === "video") return <VideoPlayer assetId={a.id} className={className} />;
  if (kind === "audio") return <audio controls src={assetUrl(a.id)} className="w-full" crossOrigin="use-credentials" data-testid="audio-player" />;
  return <div className="flex aspect-square w-full items-center justify-center rounded-lg bg-slate-100 text-xs text-slate-500">{a.mime_type}</div>;
}

export function AssetDetail({ id, onDeleted }: { id: string; onDeleted: () => void }) {
  const qc = useQueryClient();
  const q = useQuery<Asset>({ queryKey: ["asset", id], queryFn: () => api(`/assets/${id}`) });
  const versions = useQuery<Asset[]>({ queryKey: ["asset-versions", id], queryFn: () => api(`/assets/${id}/versions`) });
  const [form, setForm] = useState({ name: "", tags: "", usage_rights: "UNKNOWN", rights_note: "", description: "" });
  const fileRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  useEffect(() => {
    if (q.data) setForm({ name: q.data.name, tags: q.data.tags.join(", "), usage_rights: q.data.usage_rights, rights_note: q.data.rights_note, description: q.data.description });
  }, [q.data]);
  const save = useAction(() => api<Asset>(`/assets/${id}`, { method: "PATCH", body: { ...form, tags: form.tags.split(",").map((t) => t.trim()).filter(Boolean) } }),
    { success: "Đã lưu thông tin tài nguyên", invalidate: [["asset", id], ["assets"]] });
  const newVersion = async () => {
    const f = fileRef.current?.files?.[0];
    if (!f) { toast.error("Chọn file phiên bản mới"); return; }
    const fd = new FormData(); fd.append("file", f);
    setUploading(true);
    try {
      const a = await api<Asset>(`/assets/${id}/versions`, { form: fd });
      toast.success(`Đã tạo phiên bản v${a.version_no}`);
      qc.invalidateQueries({ queryKey: ["assets"] });
      onDeleted(); // chuyển sang danh sách (phiên bản mới thay thế)
    } catch (e) { toast.error(errorMessage(e)); } finally { setUploading(false); }
  };
  return (
    <Card data-testid="asset-detail">
      {q.data ? (() => { const a = q.data; return (<>
        <CardHeader><CardTitle className="truncate">{a.name}</CardTitle>
          <div className="flex flex-wrap gap-1"><Badge>{ASSET_TYPES[a.asset_type] ?? a.asset_type}</Badge><Badge variant="gray">v{a.version_no}</Badge><Badge variant="gray">{USAGE_RIGHTS[a.usage_rights] ?? a.usage_rights}</Badge>{a.data_mode === "DEMO" && <Badge variant="yellow">DEMO</Badge>}</div>
        </CardHeader>
        <CardContent className="space-y-3 text-sm">
          <Preview a={a} className="max-h-80" />
          <dl className="grid grid-cols-2 gap-x-3 gap-y-1 text-xs" data-testid="asset-meta">
            <dt className="text-slate-500">Định dạng</dt><dd>{a.mime_type}</dd>
            <dt className="text-slate-500">Dung lượng</dt><dd>{formatBytes(a.size_bytes)}</dd>
            <dt className="text-slate-500">Kích thước</dt><dd>{a.width && a.height ? `${a.width}×${a.height}` : "—"}</dd>
            <dt className="text-slate-500">Thời lượng</dt><dd>{a.duration_sec ? `${a.duration_sec.toFixed(1)}s` : "—"}</dd>
            <dt className="text-slate-500">Nguồn</dt><dd>{a.source}</dd>
            <dt className="text-slate-500">Tạo lúc</dt><dd>{formatDate(a.created_at)}</dd>
            <dt className="text-slate-500">SHA-256</dt><dd className="break-all font-mono text-[10px]">{a.checksum_sha256}</dd>
          </dl>
          <Button size="sm" variant="outline" asChild><a href={assetUrl(a.id, true)} data-testid="asset-download"><Download />Tải xuống</a></Button>
          <Can perm="asset.upload">
            <div className="space-y-2 border-t border-slate-100 pt-3">
              <Field label="Tên"><Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></Field>
              <Field label="Tag (phẩy)"><Input value={form.tags} onChange={(e) => setForm({ ...form, tags: e.target.value })} data-testid="asset-tags" /></Field>
              <Field label="Quyền sử dụng"><NativeSelect value={form.usage_rights} onChange={(e) => setForm({ ...form, usage_rights: e.target.value })} data-testid="asset-rights">{Object.entries(USAGE_RIGHTS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</NativeSelect></Field>
              <Field label="Ghi chú quyền"><Input value={form.rights_note} onChange={(e) => setForm({ ...form, rights_note: e.target.value })} /></Field>
              <Field label="Mô tả"><Textarea value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} /></Field>
              <Button size="sm" onClick={() => save.mutate(undefined)} loading={save.isPending} data-testid="asset-save">Lưu</Button>
            </div>
            <div className="space-y-2 border-t border-slate-100 pt-3">
              <p className="font-medium">Tải phiên bản mới</p>
              <div className="flex gap-2"><Input ref={fileRef} type="file" data-testid="asset-version-file" /><Button size="sm" onClick={newVersion} loading={uploading} data-testid="asset-version-submit"><Upload />Tải lên</Button></div>
            </div>
          </Can>
          <div className="border-t border-slate-100 pt-3">
            <p className="mb-1 font-medium">Lịch sử phiên bản</p>
            <ul className="space-y-1 text-xs" data-testid="asset-versions">
              {(versions.data ?? []).map((v) => <li key={v.id} className="flex justify-between"><span>v{v.version_no} · {v.name}</span><span className="text-slate-500">{formatDate(v.created_at)} · {formatBytes(v.size_bytes)}</span></li>)}
            </ul>
          </div>
          <Can perm="asset.delete">
            <ConfirmButton size="sm" variant="destructive" title="Xoá tài nguyên?" description="Xoá mềm — dữ liệu vẫn được lưu vết trong audit log." data-testid="asset-delete"
              onConfirm={async () => { await api(`/assets/${id}`, { method: "DELETE" }); toast.success("Đã xoá"); qc.invalidateQueries({ queryKey: ["assets"] }); onDeleted(); }}>
              <Trash2 />Xoá
            </ConfirmButton>
          </Can>
        </CardContent>
      </>); })() : <CardContent className="pt-5 text-sm text-slate-500">{q.error ? errorMessage(q.error) : "Đang tải…"}</CardContent>}
    </Card>
  );
}
