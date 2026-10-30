"use client";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { PlugZap, Settings2 } from "lucide-react";
import { api } from "@/lib/api";
import { useAction } from "@/hooks/use-mutate";
import { QueryView } from "@/components/app/states";
import { Field } from "@/components/app/field";
import { Button } from "@/components/ui/button";
import { Badge, type BadgeVariant } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Textarea } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { formatDate, formatVND } from "@/lib/utils";

type Provider = { id: string; provider_type: string; provider_code: string; name: string; is_enabled: boolean; config: Record<string, unknown>; secret_last4: string | null; connection_status: string; last_verified_at: string | null; last_error: string | null; unit_cost: string; cost_unit: string };
const CONN: Record<string, { label: string; variant: BadgeVariant }> = {
  NOT_CONFIGURED: { label: "Chưa kết nối", variant: "gray" },
  CONFIGURED_UNVERIFIED: { label: "Đã nhập key — chưa xác minh", variant: "yellow" },
  VERIFIED: { label: "Đã xác minh", variant: "green" },
  ERROR: { label: "Lỗi kết nối", variant: "red" },
  BUILTIN: { label: "Tích hợp sẵn", variant: "default" },
};

function Edit({ p, onClose }: { p: Provider; onClose: () => void }) {
  const [config, setConfig] = useState(JSON.stringify(p.config, null, 2));
  const [key, setKey] = useState("");
  const [keyFile, setKeyFile] = useState("");
  const [cost, setCost] = useState(String(Number(p.unit_cost)));
  let parsed: Record<string, unknown> | null = null;
  try { parsed = JSON.parse(config); } catch { parsed = null; }
  const save = useAction(() => {
    const body: Record<string, unknown> = { config: parsed, unit_cost: Number(cost) };
    if (key) body.api_key = key;
    return api(`/admin/providers/${p.id}`, { method: "PATCH", body });
  }, { success: "Đã lưu kết nối (API key được mã hoá)", invalidate: [["admin-providers"]], onSuccess: onClose });
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent wide>
        <DialogHeader><DialogTitle>{p.name}</DialogTitle></DialogHeader>
        <div className="space-y-3">
          <Field label="Cấu hình (JSON, KHÔNG chứa secret)" error={parsed ? undefined : "JSON không hợp lệ"}>
            <Textarea rows={8} className="font-mono text-xs" value={config} onChange={(e) => setConfig(e.target.value)} data-testid="prov-config" />
          </Field>
          {p.config.adapter === "flow_cdp" && (
            <p className="rounded-md bg-amber-50 p-2 text-sm text-amber-800" data-testid="prov-flow-cdp-note">
              Không cần API key: chạy <code>scripts\windows\start-flow-chrome.ps1</code>, đăng nhập Flow trong cửa sổ Chrome đó, rồi bấm “Kiểm tra”.
            </p>
          )}
          {p.connection_status !== "BUILTIN" && p.config.adapter !== "flow_cdp" && (
            <Field label={`API key ${p.secret_last4 ? `(hiện tại: ****${p.secret_last4})` : "(chưa có)"}`} hint="Để trống nếu không đổi. Key được mã hoá, không bao giờ hiển thị lại đầy đủ.">
              <Input type="password" autoComplete="off" value={key} onChange={(e) => setKey(e.target.value)} data-testid="prov-key" />
            </Field>
          )}
          {p.config.adapter === "veo_vertex" && (
            <Field label="Hoặc nạp file khoá service account (.json)" hint={keyFile ? `Đã đọc ${keyFile} — bấm Lưu để mã hoá & lưu` : "Google Cloud → IAM → Service accounts → Keys → Add key → JSON"}>
              <Input type="file" accept="application/json,.json" data-testid="prov-key-file"
                onChange={async (e) => { const f = e.target.files?.[0]; if (f) { setKey((await f.text()).trim()); setKeyFile(f.name); } }} />
            </Field>
          )}
          <Field label={`Đơn giá (VND / ${p.cost_unit})`}><Input type="number" min={0} value={cost} onChange={(e) => setCost(e.target.value)} data-testid="prov-cost" /></Field>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Huỷ</Button>
          <Button disabled={!parsed || (key.length > 0 && key.length < 8)} loading={save.isPending} onClick={() => save.mutate(undefined)} data-testid="prov-save">Lưu</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export function ProvidersTab() {
  const q = useQuery<Provider[]>({ queryKey: ["admin-providers"], queryFn: () => api("/admin/providers") });
  const [edit, setEdit] = useState<Provider | null>(null);
  const toggle = useAction((v: { id: string; on: boolean }) => api(`/admin/providers/${v.id}`, { method: "PATCH", body: { is_enabled: v.on } }),
    { success: "Đã cập nhật", invalidate: [["admin-providers"]] });
  const test = useAction((id: string) => api<Provider>(`/admin/providers/${id}/test`, { method: "POST" }),
    { success: (r) => `Kết quả: ${CONN[r.connection_status]?.label ?? r.connection_status}`, invalidate: [["admin-providers"]] });
  return (
    <Card>
      <CardHeader><CardTitle>API Connections & AI Providers</CardTitle>
        <p className="text-sm text-slate-500">Chỉ đánh dấu “Đã xác minh” khi gọi API chính thức thành công. Mock Provider không phải kết nối thật.</p></CardHeader>
      <CardContent>
        <QueryView q={q}>
          {(list) => (
            <Table data-testid="providers-table">
              <THead><TR><TH>Loại</TH><TH>Nhà cung cấp</TH><TH>Trạng thái kết nối</TH><TH>API key</TH><TH>Đơn giá</TH><TH>Xác minh</TH><TH>Bật</TH><TH></TH></TR></THead>
              <TBody>
                {list.map((p) => (
                  <TR key={p.id} data-testid={`prov-${p.provider_code}`}>
                    <TD><Badge variant="gray">{p.provider_type}</Badge></TD>
                    <TD><p className="font-medium">{p.name}</p><p className="font-mono text-xs text-slate-500">{p.provider_code}</p>{typeof p.config.note === "string" && <p className="text-xs text-slate-500">{p.config.note}</p>}</TD>
                    <TD><Badge variant={CONN[p.connection_status]?.variant ?? "gray"} data-testid="prov-status">{CONN[p.connection_status]?.label ?? p.connection_status}</Badge>{p.last_error && <p className="mt-1 max-w-xs text-xs text-red-700">{p.last_error}</p>}</TD>
                    <TD className="font-mono text-xs" data-testid="prov-secret">{p.secret_last4 ? `****${p.secret_last4}` : "—"}</TD>
                    <TD className="text-xs">{formatVND(p.unit_cost)}/{p.cost_unit}</TD>
                    <TD className="text-xs">{formatDate(p.last_verified_at)}</TD>
                    <TD><Switch checked={p.is_enabled} onCheckedChange={(on) => toggle.mutate({ id: p.id, on })} aria-label="Bật" /></TD>
                    <TD className="space-x-1 whitespace-nowrap">
                      <Button size="sm" variant="ghost" onClick={() => setEdit(p)} data-testid="prov-edit"><Settings2 />Sửa</Button>
                      {p.connection_status !== "BUILTIN" && <Button size="sm" variant="ghost" onClick={() => test.mutate(p.id)} data-testid="prov-test"><PlugZap />Test</Button>}
                    </TD>
                  </TR>
                ))}
              </TBody>
            </Table>
          )}
        </QueryView>
      </CardContent>
      {edit && <Edit p={edit} onClose={() => setEdit(null)} />}
    </Card>
  );
}
