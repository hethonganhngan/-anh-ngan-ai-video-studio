"use client";
import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, DatabaseBackup, Plus, Trash2, XCircle } from "lucide-react";
import { api } from "@/lib/api";
import { useAction } from "@/hooks/use-mutate";
import { useAuth } from "@/hooks/use-auth";
import { EmptyState, QueryView } from "@/components/app/states";
import { Field } from "@/components/app/field";
import { ConfirmButton } from "@/components/app/confirm";
import { ModeBadge } from "@/components/app/status-badge";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, NativeSelect } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { useChannels } from "@/hooks/use-lookups";
import { formatBytes, formatDate, formatVND } from "@/lib/utils";
import type { Page } from "@/types/api";

// ---------- Health / Storage ----------
type Health = { status: string; version: string; uptime_sec: number; mode: string; checks: Record<string, { ok: boolean; [k: string]: unknown }>; worker: Record<string, unknown> };
const CHECK_LABEL: Record<string, string> = { database: "PostgreSQL", redis: "Redis", ffmpeg: "FFmpeg / FFprobe", storage: "Object Storage", worker: "Celery Worker" };

export function HealthTab() {
  const q = useQuery<Health>({ queryKey: ["admin-health"], queryFn: () => api("/admin/health"), refetchInterval: 15000 });
  return (
    <Card>
      <CardHeader><CardTitle>Storage & System Health</CardTitle></CardHeader>
      <CardContent>
        <QueryView q={q}>
          {(h) => (
            <div className="space-y-3" data-testid="health">
              <div className="flex flex-wrap items-center gap-3 text-sm">
                <Badge variant={h.status === "ok" ? "green" : "orange"} data-testid="health-status">{h.status === "ok" ? "Hoạt động bình thường" : "Suy giảm"}</Badge>
                <span>Phiên bản {h.version}</span><span>Uptime {Math.round(h.uptime_sec / 60)} phút</span><ModeBadge mode={h.mode} />
              </div>
              <div className="grid gap-2 md:grid-cols-3">
                {Object.entries({ ...h.checks, worker: h.worker }).map(([k, v]) => (
                  <div key={k} className="flex items-start gap-2 rounded-lg border border-slate-200 p-3" data-testid={`check-${k}`}>
                    {v.ok ? <CheckCircle2 className="h-5 w-5 text-emerald-600" /> : <XCircle className="h-5 w-5 text-red-600" />}
                    <div className="text-sm">
                      <p className="font-medium">{CHECK_LABEL[k] ?? k}</p>
                      <p className="text-xs text-slate-500">{Object.entries(v).filter(([kk]) => kk !== "ok").map(([kk, vv]) => `${kk}: ${String(vv)}`).join(" · ") || (v.ok ? "OK" : "Lỗi")}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </QueryView>
      </CardContent>
    </Card>
  );
}

// ---------- Budgets & costs ----------
type Budget = { id: string; scope: string; scope_ref: string; period: string; limit_amount: string; alert_threshold_pct: number; hard_stop: boolean; data_mode: string };
type Costs = { total: number; simulated_total: number; by_category: Record<string, number>; by_provider: Record<string, number>; items: { id: string; created_at: string; category: string; provider_code: string; amount: number; is_simulated: boolean; description: string }[] };

export function BudgetTab() {
  const { has } = useAuth();
  const channels = useChannels();
  const q = useQuery<Budget[]>({ queryKey: ["admin-budgets"], queryFn: () => api("/admin/budgets") });
  const costs = useQuery<Costs>({ queryKey: ["admin-costs"], queryFn: () => api("/admin/costs") });
  const [f, setF] = useState({ scope: "GLOBAL", scope_ref: "*", period: "MONTHLY", limit_amount: 5000000, alert_threshold_pct: 80, hard_stop: true });
  const save = useAction(() => api("/admin/budgets", { body: f }), { success: "Đã lưu hạn mức", invalidate: [["admin-budgets"], ["dashboard"]] });
  const del = useAction((id: string) => api(`/admin/budgets/${id}`, { method: "DELETE" }), { success: "Đã xoá hạn mức", invalidate: [["admin-budgets"]] });
  const scopeName = (b: Budget) => b.scope === "CHANNEL" ? channels.data?.find((c) => c.id === b.scope_ref)?.name ?? b.scope_ref : b.scope_ref;
  return (
    <div className="space-y-4">
      <Card>
        <CardHeader><CardTitle>Hạn mức ngân sách</CardTitle><p className="text-sm text-slate-500">Hard stop: chặn mọi tác vụ phát sinh chi phí khi vượt hạn mức. Hạn mức tách riêng theo chế độ DEMO/PRODUCTION.</p></CardHeader>
        <CardContent className="space-y-3">
          <QueryView q={q} isEmpty={(d) => d.length === 0} empty={<EmptyState title="Chưa có hạn mức" />}>
            {(list) => (
              <Table data-testid="budgets-table">
                <THead><TR><TH>Phạm vi</TH><TH>Đối tượng</TH><TH>Kỳ</TH><TH>Hạn mức</TH><TH>Cảnh báo</TH><TH>Hard stop</TH><TH></TH></TR></THead>
                <TBody>
                  {list.map((b) => (
                    <TR key={b.id} data-testid="budget-row">
                      <TD>{b.scope}</TD><TD>{scopeName(b)}</TD><TD>{b.period === "MONTHLY" ? "Tháng" : "Ngày"}</TD>
                      <TD className="font-medium">{formatVND(b.limit_amount)}</TD><TD>{b.alert_threshold_pct}%</TD>
                      <TD>{b.hard_stop ? <Badge variant="red">Chặn</Badge> : <Badge variant="gray">Chỉ cảnh báo</Badge>}</TD>
                      <TD>{has("admin.budget") && <Button size="sm" variant="ghost" onClick={() => del.mutate(b.id)} data-testid="budget-delete"><Trash2 /></Button>}</TD>
                    </TR>
                  ))}
                </TBody>
              </Table>
            )}
          </QueryView>
          {has("admin.budget") && (
            <div className="grid items-end gap-2 rounded-lg bg-slate-50 p-3 md:grid-cols-7">
              <Field label="Phạm vi"><NativeSelect value={f.scope} onChange={(e) => setF({ ...f, scope: e.target.value, scope_ref: e.target.value === "GLOBAL" ? "*" : "" })} data-testid="b-scope">
                <option value="GLOBAL">Toàn hệ thống</option><option value="CHANNEL">Kênh</option><option value="PROVIDER">Nhà cung cấp</option></NativeSelect></Field>
              <Field label="Đối tượng">
                {f.scope === "CHANNEL" ? (
                  <NativeSelect value={f.scope_ref} onChange={(e) => setF({ ...f, scope_ref: e.target.value })} data-testid="b-ref"><option value="">—</option>{(channels.data ?? []).map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</NativeSelect>
                ) : <Input value={f.scope_ref} disabled={f.scope === "GLOBAL"} onChange={(e) => setF({ ...f, scope_ref: e.target.value })} placeholder="mock / veo_vertex…" data-testid="b-ref" />}
              </Field>
              <Field label="Kỳ"><NativeSelect value={f.period} onChange={(e) => setF({ ...f, period: e.target.value })} data-testid="b-period"><option value="MONTHLY">Tháng</option><option value="DAILY">Ngày</option></NativeSelect></Field>
              <Field label="Hạn mức (VND)"><Input type="number" min={0} value={f.limit_amount} onChange={(e) => setF({ ...f, limit_amount: Number(e.target.value) })} data-testid="b-limit" /></Field>
              <Field label="Cảnh báo (%)"><Input type="number" min={1} max={100} value={f.alert_threshold_pct} onChange={(e) => setF({ ...f, alert_threshold_pct: Number(e.target.value) })} /></Field>
              <label className="flex items-center gap-2 pb-2 text-sm"><Switch checked={f.hard_stop} onCheckedChange={(v) => setF({ ...f, hard_stop: v })} />Hard stop</label>
              <Button onClick={() => save.mutate(undefined)} disabled={!f.scope_ref} loading={save.isPending} data-testid="b-save"><Plus />Lưu</Button>
            </div>
          )}
        </CardContent>
      </Card>
      <Card>
        <CardHeader><CardTitle>Chi phí phát sinh (500 bản ghi gần nhất)</CardTitle></CardHeader>
        <CardContent>
          <QueryView q={costs}>
            {(c) => (
              <div className="space-y-3" data-testid="costs">
                <div className="flex flex-wrap gap-4 text-sm">
                  <span>Tổng: <b data-testid="costs-total">{formatVND(c.total)}</b></span>
                  {c.simulated_total > 0 && <span className="text-amber-700">Trong đó mô phỏng: {formatVND(c.simulated_total)}</span>}
                  {Object.entries(c.by_category).map(([k, v]) => <Badge key={k} variant="gray">{k}: {formatVND(v)}</Badge>)}
                  {Object.entries(c.by_provider).map(([k, v]) => <Badge key={k} variant="default">{k}: {formatVND(v)}</Badge>)}
                </div>
                <Table>
                  <THead><TR><TH>Thời gian</TH><TH>Loại</TH><TH>Provider</TH><TH>Số tiền</TH><TH>Mô tả</TH></TR></THead>
                  <TBody>
                    {c.items.slice(0, 50).map((i) => (
                      <TR key={i.id}><TD className="text-xs">{formatDate(i.created_at)}</TD><TD>{i.category}</TD><TD>{i.provider_code}</TD>
                        <TD>{formatVND(i.amount)} {i.is_simulated && <Badge variant="yellow">mô phỏng</Badge>}</TD><TD className="text-xs">{i.description}</TD></TR>
                    ))}
                  </TBody>
                </Table>
              </div>
            )}
          </QueryView>
        </CardContent>
      </Card>
    </div>
  );
}

// ---------- Policies & notifications ----------
type Settings = Record<string, Record<string, unknown>>;
export function PoliciesTab() {
  const q = useQuery<Settings>({ queryKey: ["admin-settings"], queryFn: () => api("/admin/settings") });
  const [qc, setQc] = useState({ min_total: 98, require_human_review: true });
  const [gen, setGen] = useState({ max_retries: 3, scene_seconds: 8, max_dialogue_lines: 2 });
  const [noti, setNoti] = useState({ budget_alert: true, qc_failed: true, feedback_p0: true, email_enabled: false });
  useEffect(() => {
    if (!q.data) return;
    const s = q.data;
    setQc({ min_total: Number(s["qc.policy"].min_total), require_human_review: Boolean(s["qc.policy"].require_human_review) });
    setGen({ max_retries: Number(s["generation.policy"].max_retries), scene_seconds: Number(s["generation.policy"].scene_seconds), max_dialogue_lines: Number(s["generation.policy"].max_dialogue_lines) });
    const n = s["notifications"];
    setNoti({ budget_alert: !!n.budget_alert, qc_failed: !!n.qc_failed, feedback_p0: !!n.feedback_p0, email_enabled: !!n.email_enabled });
  }, [q.data]);
  const save = useAction((v: { key: string; value: Record<string, unknown> }) => api(`/admin/settings/${v.key}`, { method: "PUT", body: { value: v.value } }),
    { success: "Đã lưu cài đặt", invalidate: [["admin-settings"]] });
  const qcOk = qc.min_total >= 90 && qc.min_total <= 100;
  return (
    <QueryView q={q}>
      {() => (
        <div className="grid gap-4 lg:grid-cols-3">
          <Card>
            <CardHeader><CardTitle>Chính sách QC</CardTitle></CardHeader>
            <CardContent className="space-y-3">
              <Field label="Điểm tối thiểu để phát hành (/100)" error={qcOk ? undefined : "Trong khoảng 90–100"}>
                <Input type="number" min={90} max={100} value={qc.min_total} onChange={(e) => setQc({ ...qc, min_total: Number(e.target.value) })} data-testid="qc-min" />
              </Field>
              <label className="flex items-center gap-2 text-sm"><Switch checked={qc.require_human_review} onCheckedChange={(v) => setQc({ ...qc, require_human_review: v })} />Bắt buộc người chấm</label>
              <Button onClick={() => save.mutate({ key: "qc.policy", value: qc })} disabled={!qcOk} data-testid="qc-save">Lưu</Button>
            </CardContent>
          </Card>
          <Card>
            <CardHeader><CardTitle>Chính sách sản xuất</CardTitle></CardHeader>
            <CardContent className="space-y-3">
              <Field label="Số lần retry tối đa / cảnh"><Input type="number" min={0} max={10} value={gen.max_retries} onChange={(e) => setGen({ ...gen, max_retries: Number(e.target.value) })} data-testid="gen-retries" /></Field>
              <Field label="Thời lượng cảnh (giây)"><Input type="number" min={4} max={10} value={gen.scene_seconds} onChange={(e) => setGen({ ...gen, scene_seconds: Number(e.target.value) })} /></Field>
              <Field label="Số câu thoại tối đa / cảnh"><Input type="number" min={1} max={4} value={gen.max_dialogue_lines} onChange={(e) => setGen({ ...gen, max_dialogue_lines: Number(e.target.value) })} /></Field>
              <Button onClick={() => save.mutate({ key: "generation.policy", value: gen })} data-testid="gen-save">Lưu</Button>
            </CardContent>
          </Card>
          <Card>
            <CardHeader><CardTitle>Thông báo</CardTitle></CardHeader>
            <CardContent className="space-y-3">
              {([["budget_alert", "Cảnh báo ngân sách"], ["qc_failed", "QC không đạt"], ["feedback_p0", "Feedback P0"], ["email_enabled", "Gửi email (cần cấu hình SMTP)"]] as const).map(([k, l]) => (
                <label key={k} className="flex items-center justify-between text-sm">{l}<Switch checked={noti[k]} onCheckedChange={(v) => setNoti({ ...noti, [k]: v })} data-testid={`noti-${k}`} /></label>
              ))}
              <Button onClick={() => save.mutate({ key: "notifications", value: noti })} data-testid="noti-save">Lưu</Button>
            </CardContent>
          </Card>
        </div>
      )}
    </QueryView>
  );
}

// ---------- Audit ----------
type Audit = { id: string; created_at: string; actor_type: string; actor_id: string | null; actor_label: string | null; action: string; entity_type: string; entity_id: string | null; before: Record<string, unknown> | null; after: Record<string, unknown> | null; ip_address: string | null; data_mode: string };
export function AuditTab() {
  const [action, setAction] = useState("");
  const [entity, setEntity] = useState("");
  const p = new URLSearchParams({ page_size: "100" });
  if (action) p.set("action", action);
  if (entity) p.set("entity_type", entity);
  const q = useQuery<Page<Audit>>({ queryKey: ["audit", p.toString()], queryFn: () => api(`/admin/audit-logs?${p}`) });
  return (
    <Card>
      <CardHeader className="flex-row flex-wrap items-center justify-between gap-2">
        <CardTitle>Audit Logs (chỉ ghi thêm, không sửa/xoá)</CardTitle>
        <div className="flex gap-2">
          <Input className="w-48" placeholder="Hành động (vd: project.)" value={action} onChange={(e) => setAction(e.target.value)} data-testid="audit-action" />
          <Input className="w-40" placeholder="Đối tượng (vd: user)" value={entity} onChange={(e) => setEntity(e.target.value)} data-testid="audit-entity" />
        </div>
      </CardHeader>
      <CardContent>
        <QueryView q={q} isEmpty={(d) => d.items.length === 0} empty={<EmptyState title="Không có bản ghi" />}>
          {(d) => (
            <Table data-testid="audit-table">
              <THead><TR><TH>Thời gian</TH><TH>Người/Agent</TH><TH>Hành động</TH><TH>Đối tượng</TH><TH>Thay đổi</TH><TH>IP</TH></TR></THead>
              <TBody>
                {d.items.map((a) => (
                  <TR key={a.id} data-testid="audit-row">
                    <TD className="text-xs">{formatDate(a.created_at)}</TD>
                    <TD className="text-xs">{a.actor_type === "AGENT" ? `Agent ${a.actor_id}` : a.actor_label ?? a.actor_type}</TD>
                    <TD className="font-mono text-xs">{a.action}</TD>
                    <TD className="text-xs">{a.entity_type} {a.entity_id?.slice(0, 8)}</TD>
                    <TD className="max-w-md text-xs"><code className="break-all">{a.after ? JSON.stringify(a.after).slice(0, 160) : ""}</code></TD>
                    <TD className="text-xs">{a.ip_address}</TD>
                  </TR>
                ))}
              </TBody>
            </Table>
          )}
        </QueryView>
        <p className="mt-2 text-xs text-slate-500">Tổng {q.data?.total ?? 0} bản ghi.</p>
      </CardContent>
    </Card>
  );
}

// ---------- Backup ----------
type Backups = { files: { file_name: string; size_bytes: number; created_at: string }[]; records: { id: string; file_name: string; status: string; checksum: string | null; note: string; created_at: string }[] };
export function BackupTab() {
  const { me } = useAuth();
  const q = useQuery<Backups>({ queryKey: ["admin-backups"], queryFn: () => api("/admin/backups") });
  const [media, setMedia] = useState(false);
  const [note, setNote] = useState("");
  const create = useAction(() => api<{ file_name: string }>("/admin/backups", { body: { include_media: media, note } }),
    { success: (r) => `Đã sao lưu ${r.file_name}`, invalidate: [["admin-backups"]] });
  const superAdmin = me?.role.code === "SUPER_ADMIN";
  return (
    <Card>
      <CardHeader><CardTitle>Sao lưu & khôi phục</CardTitle><p className="text-sm text-slate-500">pg_dump định dạng custom; tuỳ chọn nén thư mục media (storage local). Khôi phục chỉ dành cho Super Admin.</p></CardHeader>
      <CardContent className="space-y-4">
        <div className="flex flex-wrap items-end gap-3">
          <Field label="Ghi chú"><Input value={note} onChange={(e) => setNote(e.target.value)} data-testid="backup-note" /></Field>
          <label className="flex items-center gap-2 pb-2 text-sm"><Switch checked={media} onCheckedChange={setMedia} />Kèm media</label>
          <Button onClick={() => create.mutate(undefined)} loading={create.isPending} data-testid="backup-create"><DatabaseBackup />Tạo bản sao lưu</Button>
        </div>
        <QueryView q={q} isEmpty={(d) => d.files.length === 0} empty={<EmptyState title="Chưa có bản sao lưu" />}>
          {(d) => (
            <Table data-testid="backups-table">
              <THead><TR><TH>File</TH><TH>Dung lượng</TH><TH>Thời gian</TH><TH></TH></TR></THead>
              <TBody>
                {d.files.map((f) => (
                  <TR key={f.file_name} data-testid="backup-row">
                    <TD className="font-mono text-xs">{f.file_name}</TD><TD>{formatBytes(f.size_bytes)}</TD><TD className="text-xs">{formatDate(f.created_at)}</TD>
                    <TD>{superAdmin && f.file_name.endsWith(".dump") && (
                      <ConfirmButton size="sm" variant="destructive" title="Khôi phục dữ liệu?" description="Toàn bộ dữ liệu hiện tại sẽ được thay bằng bản sao lưu. Không thể hoàn tác."
                        requireText={`RESTORE ${f.file_name}`} confirmLabel="Khôi phục" data-testid="backup-restore"
                        onConfirm={async () => { await api("/admin/backups/restore", { body: { file_name: f.file_name, confirm_text: `RESTORE ${f.file_name}` } }); window.location.reload(); }}>
                        Khôi phục
                      </ConfirmButton>
                    )}</TD>
                  </TR>
                ))}
              </TBody>
            </Table>
          )}
        </QueryView>
      </CardContent>
    </Card>
  );
}

// ---------- Mode ----------
export function ModeTab() {
  const { me, refresh, has } = useAuth();
  const target = me?.mode === "DEMO" ? "PRODUCTION" : "DEMO";
  return (
    <Card>
      <CardHeader><CardTitle>Demo / Production Mode</CardTitle></CardHeader>
      <CardContent className="space-y-3 text-sm">
        <p>Chế độ hiện tại: <ModeBadge mode={me?.mode} /></p>
        <ul className="list-disc space-y-1 pl-5 text-slate-600">
          <li><b>DEMO</b>: Mock AI, Mock Video Provider, dữ liệu mẫu gắn nhãn DEMO, không gọi API tính phí, không xuất bản thật.</li>
          <li><b>PRODUCTION</b>: chỉ dùng API thật đã được cấp quyền, chi phí thật, bắt buộc phê duyệt, Mock Provider bị chặn.</li>
          <li>Dữ liệu hai chế độ tách biệt: chuyển chế độ không làm mất dữ liệu của chế độ kia.</li>
        </ul>
        {has("admin.mode") ? (
          <ConfirmButton variant={target === "PRODUCTION" ? "destructive" : "default"} title={`Chuyển sang ${target}?`}
            description={target === "PRODUCTION" ? "Từ giờ mọi tác vụ có thể phát sinh chi phí thật." : "Hệ thống sẽ hiển thị dữ liệu DEMO."}
            requireText={target} data-testid="mode-switch"
            onConfirm={async () => { await api("/admin/mode", { body: { mode: target, confirm_text: target } }); refresh(); window.location.reload(); }}>
            Chuyển sang {target}
          </ConfirmButton>
        ) : <p className="text-slate-500">Bạn không có quyền chuyển chế độ.</p>}
      </CardContent>
    </Card>
  );
}
