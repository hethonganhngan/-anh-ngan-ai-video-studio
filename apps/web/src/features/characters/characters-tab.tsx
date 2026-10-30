"use client";
import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Lock as LockIcon, Pencil, Plus, Save, Trash2, Upload, X } from "lucide-react";
import { toast } from "sonner";
import { api, errorMessage } from "@/lib/api";
import { useAuth } from "@/hooks/use-auth";
import { useChannels } from "@/hooks/use-lookups";
import { ConfirmButton } from "@/components/app/confirm";
import { Can } from "@/components/app/require";
import { EmptyState, QueryView } from "@/components/app/states";
import { AssetImage } from "@/components/app/media";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Input, NativeSelect, Textarea } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";
import type { Character, Lock, Voice } from "@/types/api";
import { LockHistory } from "./lock-history";
import { uploadAsset } from "./upload-asset";

type Detail = { character: Character; locks: Lock[]; readiness: { ready: boolean; issues: string[]; references: Record<string, string> } };
const REFS: [string, string][] = [["FRONT", "Ảnh chính diện"], ["THREE_QUARTER", "Ảnh góc 3/4"], ["FULL_BODY", "Ảnh toàn thân"], ["EXPRESSION", "Biểu cảm"], ["OUTFIT", "Trang phục"]];
const CONSENT: Record<string, string> = { NOT_REQUIRED: "Không cần (nhân vật AI)", PENDING: "Chờ xác nhận", GRANTED: "Đã đồng ý", REVOKED: "Đã thu hồi" };

type Form = { name: string; description: string; age_range: string; gender: string; appearance: string; outfit: string; expressions: string; personality: string; channel_id: string; voice_profile_id: string; consent_status: string; usage_rights: string };
const emptyForm: Form = { name: "", description: "", age_range: "", gender: "", appearance: "", outfit: "", expressions: "", personality: "", channel_id: "", voice_profile_id: "", consent_status: "NOT_REQUIRED", usage_rights: "" };
const toBody = (f: Form) => ({ ...f, expressions: f.expressions.split(",").map((x) => x.trim()).filter(Boolean), channel_id: f.channel_id || null, voice_profile_id: f.voice_profile_id || null });

function CharacterForm({ initial, onSubmit, busy, submitLabel }: { initial: Form; onSubmit: (f: Form) => void; busy: boolean; submitLabel: string }) {
  const [f, setF] = useState(initial);
  const initKey = JSON.stringify(initial);
  useEffect(() => setF(JSON.parse(initKey)), [initKey]);
  const channels = useChannels();
  const voices = useQuery<Voice[]>({ queryKey: ["voices"], queryFn: () => api("/voices") });
  const set = (k: keyof Form, v: string) => setF({ ...f, [k]: v });
  return (
    <form className="grid gap-2 md:grid-cols-2" onSubmit={(e) => { e.preventDefault(); if (!f.name.trim()) { toast.error("Nhập tên nhân vật"); return; } onSubmit(f); }} data-testid="character-form">
      <div><Label>Tên nhân vật *</Label><Input value={f.name} onChange={(e) => set("name", e.target.value)} data-testid="char-name" /></div>
      <div><Label>Kênh</Label><NativeSelect value={f.channel_id} onChange={(e) => set("channel_id", e.target.value)}><option value="">— Dùng chung —</option>{(channels.data ?? []).map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</NativeSelect></div>
      <div><Label>Độ tuổi</Label><Input value={f.age_range} onChange={(e) => set("age_range", e.target.value)} /></div>
      <div><Label>Giới tính</Label><Input value={f.gender} onChange={(e) => set("gender", e.target.value)} /></div>
      <div className="md:col-span-2"><Label>Mô tả</Label><Textarea rows={2} value={f.description} onChange={(e) => set("description", e.target.value)} /></div>
      <div className="md:col-span-2"><Label>Ngoại hình (bắt buộc để khoá)</Label><Textarea rows={2} value={f.appearance} onChange={(e) => set("appearance", e.target.value)} data-testid="char-appearance" /></div>
      <div className="md:col-span-2"><Label>Trang phục (bắt buộc để khoá)</Label><Textarea rows={2} value={f.outfit} onChange={(e) => set("outfit", e.target.value)} data-testid="char-outfit" /></div>
      <div><Label>Biểu cảm (phân cách dấu phẩy)</Label><Input value={f.expressions} onChange={(e) => set("expressions", e.target.value)} /></div>
      <div><Label>Tính cách</Label><Input value={f.personality} onChange={(e) => set("personality", e.target.value)} /></div>
      <div><Label>Giọng nói</Label><NativeSelect value={f.voice_profile_id} onChange={(e) => set("voice_profile_id", e.target.value)}><option value="">— Chưa gán —</option>{(voices.data ?? []).map((v) => <option key={v.id} value={v.id}>{v.code} · {v.name}</option>)}</NativeSelect></div>
      <div><Label>Consent hình ảnh</Label><NativeSelect value={f.consent_status} onChange={(e) => set("consent_status", e.target.value)} data-testid="char-consent">{Object.entries(CONSENT).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</NativeSelect></div>
      <div className="md:col-span-2"><Label>Quyền sử dụng / Usage rights</Label><Input value={f.usage_rights} onChange={(e) => set("usage_rights", e.target.value)} /></div>
      <div className="md:col-span-2 flex justify-end"><Button type="submit" loading={busy} data-testid="char-submit"><Save />{submitLabel}</Button></div>
    </form>
  );
}

function RefUpload({ charId, refType, label, assetId, onDone, channelId }: { charId: string; refType: string; label: string; assetId?: string; onDone: () => void; channelId: string | null }) {
  const [busy, setBusy] = useState(false);
  const onFile = async (file?: File) => {
    if (!file) return;
    setBusy(true);
    try {
      const a = await uploadAsset(file, "CHARACTER", { rights: "OWNED", tags: `character,${refType.toLowerCase()}`, channelId });
      await api(`/characters/${charId}/references`, { body: { ref_type: refType, asset_id: a.id } });
      toast.success(`Đã cập nhật ${label}`);
      onDone();
    } catch (e) { toast.error(errorMessage(e)); } finally { setBusy(false); }
  };
  return (
    <div className="rounded-lg border border-slate-200 p-2 text-center" data-testid={`ref-${refType}`}>
      <AssetImage assetId={assetId} alt={label} className="mx-auto h-28 w-full object-contain" />
      <p className="mt-1 text-xs font-medium">{label} {assetId ? "✓" : ""}</p>
      <Can perm="character.edit">
        <label className={cn("mt-1 inline-flex cursor-pointer items-center gap-1 rounded-md border border-slate-300 px-2 py-1 text-xs hover:bg-slate-50", busy && "opacity-50")}>
          <Upload className="h-3 w-3" />{busy ? "Đang tải…" : assetId ? "Thay ảnh" : "Tải ảnh"}
          <input type="file" accept="image/png,image/jpeg,image/webp" className="hidden" disabled={busy} onChange={(e) => onFile(e.target.files?.[0])} data-testid={`ref-file-${refType}`} />
        </label>
      </Can>
    </div>
  );
}

function CharacterSummary({ c }: { c: Character }) {
  const voices = useQuery<Voice[]>({ queryKey: ["voices"], queryFn: () => api("/voices") });
  const channels = useChannels();
  const voice = (voices.data ?? []).find((v) => v.id === c.voice_profile_id);
  const rows: [string, string | null | undefined][] = [["Kênh", (channels.data ?? []).find((x) => x.id === c.channel_id)?.name ?? "Dùng chung"],
    ["Độ tuổi", c.age_range], ["Giới tính", c.gender], ["Tính cách", c.personality], ["Biểu cảm", c.expressions.join(", ")],
    ["Giọng nói", voice ? `${voice.code} · ${voice.name}` : c.voice_profile_id ? "(giọng đã xoá)" : ""], ["Consent hình ảnh", CONSENT[c.consent_status]],
    ["Quyền sử dụng", c.usage_rights]];
  return (
    <div className="space-y-3 text-sm" data-testid="character-summary">
      {c.description && <p className="text-slate-700">{c.description}</p>}
      <p><b>Ngoại hình:</b> {c.appearance || "—"}</p>
      <p><b>Trang phục:</b> {c.outfit || "—"}</p>
      <dl className="grid gap-x-6 gap-y-1 md:grid-cols-2">
        {rows.map(([k, v]) => <div key={k} className="flex justify-between gap-2 border-b border-slate-100 py-1"><dt className="text-slate-500">{k}</dt><dd className="text-right">{v || "—"}</dd></div>)}
      </dl>
    </div>
  );
}

function CharacterDetail({ id, onDeleted }: { id: string; onDeleted: () => void }) {
  const qc = useQueryClient();
  const { has } = useAuth();
  const q = useQuery<Detail>({ queryKey: ["character", id], queryFn: () => api(`/characters/${id}`) });
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState("");
  const [editing, setEditing] = useState(false);
  useEffect(() => setEditing(false), [id]);
  const refresh = () => { qc.invalidateQueries({ queryKey: ["character", id] }); qc.invalidateQueries({ queryKey: ["characters"] }); };
  const run = async (fn: () => Promise<unknown>, ok: string) => {
    setBusy(true);
    try { await fn(); toast.success(ok); refresh(); return true; }
    catch (e) {
      const msg = errorMessage(e);
      toast.error(msg.includes("4 mắt") ? `${msg} — cần người khác có quyền duyệt` : msg);
      return false;
    } finally { setBusy(false); }
  };
  const remove = async () => {
    try { await api(`/characters/${id}`, { method: "DELETE" }); toast.success("Đã xoá nhân vật"); qc.invalidateQueries({ queryKey: ["characters"] }); onDeleted(); }
    catch (e) { toast.error(errorMessage(e)); }
  };
  return (
    <QueryView q={q}>
      {(d) => {
        const c = d.character;
        const initial: Form = { name: c.name, description: c.description, age_range: c.age_range, gender: c.gender, appearance: c.appearance, outfit: c.outfit,
          expressions: c.expressions.join(", "), personality: c.personality, channel_id: c.channel_id ?? "", voice_profile_id: c.voice_profile_id ?? "",
          consent_status: c.consent_status, usage_rights: c.usage_rights };
        const hasDraft = d.locks.some((l) => l.status === "DRAFT");
        return (
          <div className="space-y-4" data-testid="character-detail">
            <Card>
              <CardHeader>
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <CardTitle className="flex flex-wrap items-center gap-2"><span className="font-mono text-sm text-slate-500" data-testid="char-code">{c.code}</span>{c.name}
                    <Badge variant={c.status === "LOCKED" ? "green" : "gray"}>{c.status === "LOCKED" ? "Đã khoá" : "Nháp"}</Badge>{c.data_mode === "DEMO" && <Badge variant="yellow">DEMO</Badge>}</CardTitle>
                  <Can perm="character.edit"><div className="flex gap-2">
                    <Button size="sm" variant="outline" onClick={() => setEditing((x) => !x)} data-testid="char-edit">{editing ? <><X />Huỷ sửa</> : <><Pencil />Sửa</>}</Button>
                    <ConfirmButton size="sm" variant="destructive" title={`Xoá nhân vật ${c.code}?`} requireText={c.code} confirmLabel="Xoá nhân vật"
                      description="Nhân vật sẽ bị ẩn khỏi danh sách; Character Lock và ảnh tham chiếu vẫn được lưu làm lịch sử. Không xoá được khi dự án đang làm còn dùng nhân vật này."
                      onConfirm={remove} data-testid="char-delete"><Trash2 />Xoá</ConfirmButton>
                  </div></Can>
                </div>
                <CardDescription>Sửa hồ sơ không làm thay đổi Character Lock đang hiệu lực. Muốn áp dụng thay đổi phải tạo phiên bản khoá mới và duyệt.</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="mb-4 grid grid-cols-2 gap-2 md:grid-cols-5">
                  {REFS.map(([k, l]) => <RefUpload key={k} charId={c.id} refType={k} label={l} assetId={d.readiness.references[k]} onDone={refresh} channelId={c.channel_id} />)}
                </div>
                {editing && has("character.edit") ? (
                  <CharacterForm initial={initial} busy={busy} submitLabel="Lưu hồ sơ"
                    onSubmit={async (f) => { if (await run(() => api(`/characters/${c.id}`, { method: "PATCH", body: toBody(f) }), "Đã lưu hồ sơ nhân vật")) setEditing(false); }} />
                ) : <CharacterSummary c={c} />}
              </CardContent>
            </Card>
            <Card>
              <CardHeader><CardTitle className="flex items-center gap-2"><LockIcon className="h-4 w-4" />Character Lock</CardTitle></CardHeader>
              <CardContent className="space-y-3">
                <div className={cn("rounded-lg p-3 text-sm", d.readiness.ready ? "bg-emerald-50 text-emerald-800" : "bg-amber-50 text-amber-900")} data-testid="readiness">
                  {d.readiness.ready ? "✓ Đủ điều kiện tạo Character Lock" : <><p className="font-medium">Chưa đủ điều kiện khoá:</p><ul className="list-disc pl-5">{d.readiness.issues.map((i) => <li key={i}>{i}</li>)}</ul></>}
                </div>
                <Can perm="character.edit">
                  <div className="flex flex-wrap items-end gap-2">
                    <div className="flex-1"><Label>Ghi chú phiên bản khoá</Label><Input value={note} onChange={(e) => setNote(e.target.value)} placeholder="Ví dụ: khoá trang phục mùa hè" /></div>
                    <Button disabled={hasDraft} loading={busy} onClick={() => run(() => api(`/characters/${c.id}/locks`, { body: { change_note: note } }), "Đã tạo bản khoá nháp — chờ duyệt")} data-testid="create-lock">
                      <LockIcon />Tạo Character Lock
                    </Button>
                  </div>
                  {hasDraft && <p className="text-xs text-amber-700">Đang có bản khoá nháp chờ duyệt.</p>}
                </Can>
                <LockHistory locks={d.locks} activeId={c.active_lock_id} canApprove={has("character.lock_approve")} testid="char-locks"
                  onApprove={(lid) => run(() => api(`/character-locks/${lid}/approve`, { method: "POST" }), "Đã duyệt Character Lock")} />
              </CardContent>
            </Card>
          </div>
        );
      }}
    </QueryView>
  );
}

export function CharactersTab() {
  const qc = useQueryClient();
  const [search, setSearch] = useState("");
  const [sel, setSel] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [busy, setBusy] = useState(false);
  const list = useQuery<Character[]>({ queryKey: ["characters", search], queryFn: () => api(`/characters${search ? `?q=${encodeURIComponent(search)}` : ""}`) });
  const create = async (f: Form) => {
    setBusy(true);
    try {
      const c = await api<Character>("/characters", { body: toBody(f) });
      toast.success(`Đã tạo nhân vật ${c.code}`);
      setCreating(false); setSel(c.id);
      qc.invalidateQueries({ queryKey: ["characters"] });
    } catch (e) { toast.error(errorMessage(e)); } finally { setBusy(false); }
  };
  return (
    <div className="grid gap-4 lg:grid-cols-[320px_1fr]">
      <Card>
        <CardContent className="space-y-2 pt-5">
          <div className="flex gap-2">
            <Input placeholder="Tìm tên / mã…" value={search} onChange={(e) => setSearch(e.target.value)} />
            <Can perm="character.edit"><Button size="icon" onClick={() => { setCreating(true); setSel(null); }} aria-label="Tạo nhân vật" data-testid="new-character"><Plus /></Button></Can>
          </div>
          <QueryView q={list} isEmpty={(d) => d.length === 0} empty={<EmptyState title="Chưa có nhân vật" />}>
            {(d) => (
              <div className="space-y-1" data-testid="character-list">
                {d.map((c) => (
                  <button key={c.id} onClick={() => { setSel(c.id); setCreating(false); }} data-testid="character-item"
                    className={cn("flex w-full items-center justify-between rounded-lg px-3 py-2 text-left text-sm hover:bg-slate-50", sel === c.id && "bg-brand-50")}>
                    <span><span className="font-mono text-xs text-slate-500">{c.code}</span><br />{c.name}</span>
                    <Badge variant={c.status === "LOCKED" ? "green" : "gray"}>{c.status === "LOCKED" ? "Đã khoá" : "Nháp"}</Badge>
                  </button>
                ))}
              </div>
            )}
          </QueryView>
        </CardContent>
      </Card>
      <div>
        {creating ? (
          <Card><CardHeader><CardTitle>Nhân vật mới</CardTitle><CardDescription>Character ID được hệ thống sinh tự động.</CardDescription></CardHeader>
            <CardContent><CharacterForm initial={emptyForm} busy={busy} submitLabel="Tạo nhân vật" onSubmit={create} /></CardContent></Card>
        ) : sel ? <CharacterDetail id={sel} onDeleted={() => setSel(null)} /> : <EmptyState title="Chọn nhân vật" description="Chọn nhân vật bên trái hoặc tạo mới." />}
      </div>
    </div>
  );
}
