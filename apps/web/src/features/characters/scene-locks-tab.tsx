"use client";
import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, CopyPlus, Plus } from "lucide-react";
import { toast } from "sonner";
import { api, errorMessage } from "@/lib/api";
import { useChannels } from "@/hooks/use-lookups";
import { Can } from "@/components/app/require";
import { EmptyState, QueryView } from "@/components/app/states";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input, NativeSelect, Textarea } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { formatDate } from "@/lib/utils";
import type { SceneLock } from "@/types/api";
import { LOCK_STATUS } from "./lock-history";

type F = { name: string; channel_id: string; setting: string; lighting: string; props: string; colors: string; base_code: string | null };

export function SceneLocksTab() {
  const qc = useQueryClient();
  const channels = useChannels();
  const [all, setAll] = useState(false);
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [f, setF] = useState<F>({ name: "", channel_id: "", setting: "", lighting: "", props: "", colors: "", base_code: null });
  const list = useQuery<SceneLock[]>({ queryKey: ["scene-locks", all], queryFn: () => api(`/scene-locks${all ? "?all_versions=true" : ""}`) });
  const inv = () => qc.invalidateQueries({ queryKey: ["scene-locks"] });
  const submit = async () => {
    if (f.setting.trim().length < 3 || !f.name.trim()) { toast.error("Nhập tên và mô tả bối cảnh"); return; }
    setBusy(true);
    try {
      await api("/scene-locks", { body: { ...f, channel_id: f.channel_id || null } });
      toast.success(f.base_code ? `Đã tạo phiên bản mới cho ${f.base_code}` : "Đã tạo Scene Lock");
      setOpen(false); inv();
    } catch (e) { toast.error(errorMessage(e)); } finally { setBusy(false); }
  };
  const approve = async (id: string) => {
    try { await api(`/scene-locks/${id}/approve`, { method: "POST" }); toast.success("Đã duyệt Scene Lock"); inv(); } catch (e) { toast.error(errorMessage(e)); }
  };
  const openNew = (base?: SceneLock) => {
    setF(base ? { name: base.name, channel_id: base.channel_id ?? "", setting: base.lock_data.setting ?? "", lighting: base.lock_data.lighting ?? "", props: base.lock_data.props ?? "", colors: base.lock_data.colors ?? "", base_code: base.code }
      : { name: "", channel_id: "", setting: "", lighting: "", props: "", colors: "", base_code: null });
    setOpen(true);
  };
  return (
    <Card>
      <CardHeader className="flex-row flex-wrap items-center justify-between gap-2">
        <CardTitle>Scene Lock — khoá bối cảnh</CardTitle>
        <div className="flex items-center gap-2">
          <label className="flex items-center gap-1 text-sm"><input type="checkbox" checked={all} onChange={(e) => setAll(e.target.checked)} />Hiện mọi phiên bản</label>
          <Can perm="character.edit"><Button onClick={() => openNew()} data-testid="new-scene-lock"><Plus />Tạo Scene Lock</Button></Can>
        </div>
      </CardHeader>
      <CardContent>
        <QueryView q={list} isEmpty={(d) => !d.length} empty={<EmptyState title="Chưa có Scene Lock" />}>
          {(d) => (
            <Table data-testid="scene-lock-table">
              <THead><TR><TH>Mã</TH><TH>Tên</TH><TH>Bối cảnh</TH><TH>Phiên bản</TH><TH>Trạng thái</TH><TH>Tạo</TH><TH></TH></TR></THead>
              <TBody>
                {d.map((s) => (
                  <TR key={s.id} data-testid="scene-lock-row">
                    <TD className="font-mono text-xs">{s.code}</TD><TD>{s.name}</TD>
                    <TD className="max-w-xs truncate text-xs" title={s.lock_data.setting}>{s.lock_data.setting}</TD>
                    <TD>v{s.version_no}</TD>
                    <TD><Badge variant={LOCK_STATUS[s.status]?.variant ?? "gray"}>{LOCK_STATUS[s.status]?.label ?? s.status}</Badge></TD>
                    <TD className="text-xs">{formatDate(s.created_at)}</TD>
                    <TD className="space-x-1 text-right">
                      {s.status === "DRAFT" && <Can perm="character.lock_approve"><Button size="sm" variant="success" onClick={() => approve(s.id)} data-testid="approve-scene-lock"><CheckCircle2 />Duyệt</Button></Can>}
                      <Can perm="character.edit"><Button size="sm" variant="ghost" onClick={() => openNew(s)} data-testid="new-version-scene-lock"><CopyPlus />Phiên bản mới</Button></Can>
                    </TD>
                  </TR>
                ))}
              </TBody>
            </Table>
          )}
        </QueryView>
      </CardContent>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader><DialogTitle>{f.base_code ? `Phiên bản mới của ${f.base_code}` : "Scene Lock mới"}</DialogTitle></DialogHeader>
          <div className="space-y-2" data-testid="scene-lock-form">
            <div><Label>Tên</Label><Input value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} data-testid="sl-name" /></div>
            <div><Label>Kênh</Label><NativeSelect value={f.channel_id} onChange={(e) => setF({ ...f, channel_id: e.target.value })}><option value="">— Dùng chung —</option>{(channels.data ?? []).map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</NativeSelect></div>
            <div><Label>Bối cảnh *</Label><Textarea value={f.setting} onChange={(e) => setF({ ...f, setting: e.target.value })} data-testid="sl-setting" /></div>
            <div><Label>Ánh sáng</Label><Input value={f.lighting} onChange={(e) => setF({ ...f, lighting: e.target.value })} /></div>
            <div><Label>Đạo cụ</Label><Input value={f.props} onChange={(e) => setF({ ...f, props: e.target.value })} /></div>
            <div><Label>Màu chủ đạo</Label><Input value={f.colors} onChange={(e) => setF({ ...f, colors: e.target.value })} /></div>
          </div>
          <DialogFooter><Button variant="outline" onClick={() => setOpen(false)}>Huỷ</Button><Button onClick={submit} loading={busy} data-testid="sl-submit">Lưu</Button></DialogFooter>
        </DialogContent>
      </Dialog>
    </Card>
  );
}
