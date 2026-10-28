"use client";
import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Grid3X3, List, Info } from "lucide-react";
import { api } from "@/lib/api";
import { useChannels } from "@/hooks/use-lookups";
import { PageHeader } from "@/components/app/page-header";
import { RequirePermission, Can } from "@/components/app/require";
import { EmptyState, QueryView } from "@/components/app/states";
import { AssetUploader } from "@/components/app/asset-uploader";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, NativeSelect } from "@/components/ui/input";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { ASSET_TYPES, USAGE_RIGHTS } from "@/lib/labels";
import { cn, formatBytes, formatDate } from "@/lib/utils";
import { AssetDetail, Preview } from "@/features/library/asset-detail";
import type { Asset, Page } from "@/types/api";

export default function LibraryPage() {
  const qc = useQueryClient();
  const channels = useChannels();
  const [f, setF] = useState({ asset_type: "", q: "", tag: "", usage_rights: "", channel_id: "" });
  const [view, setView] = useState<"grid" | "table">("grid");
  const [sel, setSel] = useState<string | null>(null);
  const p = new URLSearchParams({ page_size: "200" });
  Object.entries(f).forEach(([k, v]) => v && p.set(k, v));
  const list = useQuery<Page<Asset>>({ queryKey: ["assets", p.toString()], queryFn: () => api(`/assets?${p}`) });
  const s = (k: keyof typeof f) => (e: { target: { value: string } }) => setF({ ...f, [k]: e.target.value });
  return (
    <RequirePermission perm="asset.view">
      <PageHeader code="M12" title="Thư viện tài nguyên" description="Ảnh, video, audio, logo, nhân vật, bối cảnh, sản phẩm, template, file tham chiếu — có quyền sử dụng, tag, phiên bản."
        actions={<div className="flex gap-1"><Button size="icon" variant={view === "grid" ? "default" : "outline"} onClick={() => setView("grid")} aria-label="Dạng lưới"><Grid3X3 /></Button><Button size="icon" variant={view === "table" ? "default" : "outline"} onClick={() => setView("table")} aria-label="Dạng bảng" data-testid="view-table"><List /></Button></div>} />
      <div className="mb-4 flex items-start gap-2 rounded-lg border border-slate-200 bg-white p-3 text-xs text-slate-600" data-testid="storage-note">
        <Info className="mt-0.5 h-4 w-4 shrink-0 text-brand-600" />
        <p>File media được lưu ở <b>Object Storage</b> (S3/MinIO hoặc local), cơ sở dữ liệu chỉ lưu metadata, checksum SHA-256 và quyền sử dụng. File tải lên được kiểm tra định dạng thực (magic bytes) và FFprobe.</p>
      </div>
      <Can perm="asset.upload">
        <Card className="mb-4"><CardHeader><CardTitle>Tải tài nguyên lên</CardTitle></CardHeader>
          <CardContent><AssetUploader channelId={f.channel_id || null} onUploaded={(a) => { qc.invalidateQueries({ queryKey: ["assets"] }); setSel(a.id); }} /></CardContent></Card>
      </Can>
      <Card className="mb-4">
        <CardContent className="grid gap-2 pt-5 md:grid-cols-5">
          <Input placeholder="Tìm tên, mô tả, tag…" value={f.q} onChange={s("q")} data-testid="lib-filter-q" />
          <NativeSelect value={f.asset_type} onChange={s("asset_type")} data-testid="lib-filter-type"><option value="">Mọi loại</option>{Object.entries(ASSET_TYPES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</NativeSelect>
          <Input placeholder="Tag chính xác" value={f.tag} onChange={s("tag")} data-testid="lib-filter-tag" />
          <NativeSelect value={f.usage_rights} onChange={s("usage_rights")}><option value="">Mọi quyền sử dụng</option>{Object.entries(USAGE_RIGHTS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</NativeSelect>
          <NativeSelect value={f.channel_id} onChange={s("channel_id")}><option value="">Mọi kênh</option>{(channels.data ?? []).map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</NativeSelect>
        </CardContent>
      </Card>
      <div className="grid gap-4 lg:grid-cols-3">
        <div className={sel ? "lg:col-span-2" : "lg:col-span-3"}>
          <QueryView q={list} isEmpty={(d) => d.items.length === 0} empty={<EmptyState title="Không có tài nguyên phù hợp" />}>
            {(d) => view === "grid" ? (
              <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-4" data-testid="lib-grid">
                {d.items.map((a) => (
                  <button key={a.id} onClick={() => setSel(a.id)} data-testid="lib-item" className={cn("overflow-hidden rounded-xl border bg-white text-left shadow-sm hover:ring-2 hover:ring-brand-500", sel === a.id ? "border-brand-500" : "border-slate-200")}>
                    {a.mime_type.startsWith("image/") ? <Preview a={a} className="aspect-square w-full" /> :
                      <div className="flex aspect-square w-full items-center justify-center bg-slate-900 text-xs text-slate-300">{a.mime_type.startsWith("video/") ? `▶ Video ${a.duration_sec ? `${a.duration_sec.toFixed(0)}s` : ""}` : a.mime_type}</div>}
                    <div className="p-2"><p className="truncate text-sm font-medium">{a.name}</p>
                      <div className="mt-1 flex flex-wrap gap-1"><Badge variant="gray">{ASSET_TYPES[a.asset_type] ?? a.asset_type}</Badge>{a.version_no > 1 && <Badge>v{a.version_no}</Badge>}{a.tags.slice(0, 2).map((t) => <Badge key={t} variant="gray">#{t}</Badge>)}</div></div>
                  </button>
                ))}
              </div>
            ) : (
              <Table data-testid="lib-table">
                <THead><TR><TH>Tên</TH><TH>Loại</TH><TH>Quyền</TH><TH>Tag</TH><TH>Dung lượng</TH><TH>Phiên bản</TH><TH>Tạo lúc</TH></TR></THead>
                <TBody>{d.items.map((a) => (
                  <TR key={a.id} onClick={() => setSel(a.id)} className="cursor-pointer" data-testid="lib-row">
                    <TD className="max-w-xs truncate">{a.name}</TD><TD>{ASSET_TYPES[a.asset_type] ?? a.asset_type}</TD><TD>{USAGE_RIGHTS[a.usage_rights] ?? a.usage_rights}</TD>
                    <TD className="text-xs">{a.tags.join(", ")}</TD><TD>{formatBytes(a.size_bytes)}</TD><TD>v{a.version_no}</TD><TD className="text-xs">{formatDate(a.created_at)}</TD>
                  </TR>))}
                </TBody>
              </Table>
            )}
          </QueryView>
        </div>
        {sel && <div><AssetDetail key={sel} id={sel} onDeleted={() => setSel(null)} /></div>}
      </div>
    </RequirePermission>
  );
}
