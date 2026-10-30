"use client";
import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Lock as LockIcon, Plus, Save } from "lucide-react";
import { toast } from "sonner";
import { api, assetUrl, errorMessage } from "@/lib/api";
import { useAuth } from "@/hooks/use-auth";
import { Can } from "@/components/app/require";
import { EmptyState, QueryView } from "@/components/app/states";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, NativeSelect } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";
import type { Lock, Voice } from "@/types/api";
import { LockHistory } from "./lock-history";
import { uploadAsset } from "./upload-asset";

const GEMINI_VOICES = ["Kore", "Aoede", "Leda", "Despina", "Sulafat", "Achernar", "Callirrhoe", "Autonoe", "Erinome", "Laomedeia", "Pulcherrima", "Vindemiatrix", "Zephyr",
  "Puck", "Charon", "Fenrir", "Orus", "Enceladus", "Iapetus", "Umbriel", "Algieba", "Algenib", "Rasalgethi", "Alnilam", "Schedar", "Gacrux", "Achird", "Zubenelgenubi", "Sadachbia", "Sadaltager"];
const CONSENT: Record<string, string> = { PENDING: "Chờ xác nhận", GRANTED: "Đã đồng ý", REVOKED: "Đã thu hồi", NOT_REQUIRED: "Không cần" };
type F = { name: string; accent: string; gender: string; age_range: string; tone: string; speaking_rate: string; provider_code: string; provider_voice_id: string; consent_status: string; usage_rights: string; audio_reference_asset_id: string; consent_document_asset_id: string };
const empty: F = { name: "", accent: "Miền Trung", gender: "", age_range: "", tone: "", speaking_rate: "vừa phải", provider_code: "manual", provider_voice_id: "", consent_status: "PENDING", usage_rights: "", audio_reference_asset_id: "", consent_document_asset_id: "" };
const toBody = (f: F) => ({ ...f, provider_voice_id: f.provider_voice_id || null, audio_reference_asset_id: f.audio_reference_asset_id || null, consent_document_asset_id: f.consent_document_asset_id || null });

function VoiceForm({ initial, onSubmit, busy, label }: { initial: F; onSubmit: (f: F) => void; busy: boolean; label: string }) {
  const [f, setF] = useState(initial);
  const [up, setUp] = useState<string | null>(null);
  const initKey = JSON.stringify(initial);
  useEffect(() => setF(JSON.parse(initKey)), [initKey]);
  const set = (k: keyof F, v: string) => setF((x) => ({ ...x, [k]: v }));
  const upload = async (file: File | undefined, kind: "audio" | "doc") => {
    if (!file) return;
    setUp(kind);
    try {
      const a = await uploadAsset(file, kind === "audio" ? "AUDIO" : "DOCUMENT", { rights: "CONSENTED", tags: kind === "audio" ? "voice,reference" : "consent" });
      set(kind === "audio" ? "audio_reference_asset_id" : "consent_document_asset_id", a.id);
      toast.success(`Đã tải ${a.name}`);
    } catch (e) { toast.error(errorMessage(e)); } finally { setUp(null); }
  };
  return (
    <form className="grid gap-2 md:grid-cols-2" data-testid="voice-form" onSubmit={(e) => { e.preventDefault(); if (!f.name.trim()) { toast.error("Nhập tên giọng"); return; } onSubmit(f); }}>
      <div><Label>Tên giọng *</Label><Input value={f.name} onChange={(e) => set("name", e.target.value)} data-testid="voice-name" /></div>
      <div><Label>Accent</Label><Input value={f.accent} onChange={(e) => set("accent", e.target.value)} data-testid="voice-accent" /></div>
      <div><Label>Giới tính</Label><Input value={f.gender} onChange={(e) => set("gender", e.target.value)} /></div>
      <div><Label>Độ tuổi</Label><Input value={f.age_range} onChange={(e) => set("age_range", e.target.value)} /></div>
      <div><Label>Chất giọng</Label><Input value={f.tone} onChange={(e) => set("tone", e.target.value)} /></div>
      <div><Label>Tốc độ</Label><Input value={f.speaking_rate} onChange={(e) => set("speaking_rate", e.target.value)} /></div>
      <div><Label>Provider</Label><NativeSelect value={f.provider_code} data-testid="voice-provider" onChange={(e) => {
        const v = e.target.value;
        setF((x) => ({ ...x, provider_code: v, ...(v === "gemini_tts" ? { provider_voice_id: GEMINI_VOICES.includes(x.provider_voice_id) ? x.provider_voice_id : "Kore", usage_rights: x.usage_rights || "Giọng AI dựng sẵn của Google Gemini TTS — dùng cho video thương mại Ánh Ngân" } : {}) }));
      }}><option value="manual">Thu âm thủ công</option><option value="gemini_tts">Gemini TTS (giọng AI tiếng Việt)</option></NativeSelect></div>
      <div><Label>Provider voice ID</Label>{f.provider_code === "gemini_tts"
        ? <NativeSelect value={f.provider_voice_id} onChange={(e) => set("provider_voice_id", e.target.value)} data-testid="voice-provider-id">{GEMINI_VOICES.map((n) => <option key={n} value={n}>{n}</option>)}</NativeSelect>
        : <Input value={f.provider_voice_id} onChange={(e) => set("provider_voice_id", e.target.value)} />}</div>
      {f.provider_code === "gemini_tts" && <p className="text-[11px] text-slate-500 md:col-span-2">Giọng AI dựng sẵn không phải giọng người thật: chọn Consent “Đã đồng ý” và ghi phạm vi sử dụng. Accent, chất giọng, tốc độ được dùng làm hướng dẫn đọc. Nghe thử từng giọng tại aistudio.google.com.</p>}
      <div>
        <Label>Audio Reference {f.audio_reference_asset_id && "✓"}</Label>
        <Input type="file" accept="audio/*" onChange={(e) => upload(e.target.files?.[0], "audio")} disabled={up === "audio"} data-testid="voice-audio-file" />
        {f.audio_reference_asset_id && <audio controls className="mt-1 w-full" src={assetUrl(f.audio_reference_asset_id)} crossOrigin="use-credentials" />}
      </div>
      <div>
        <Label>Tài liệu consent (PDF) {f.consent_document_asset_id && "✓"}</Label>
        <Input type="file" accept="application/pdf" onChange={(e) => upload(e.target.files?.[0], "doc")} disabled={up === "doc"} />
      </div>
      <div><Label>Consent / Usage Rights</Label><NativeSelect value={f.consent_status} onChange={(e) => set("consent_status", e.target.value)} data-testid="voice-consent">{Object.entries(CONSENT).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</NativeSelect></div>
      <div><Label>Phạm vi quyền sử dụng</Label><Input value={f.usage_rights} onChange={(e) => set("usage_rights", e.target.value)} /></div>
      <div className="flex justify-end md:col-span-2"><Button type="submit" loading={busy} data-testid="voice-submit"><Save />{label}</Button></div>
    </form>
  );
}

function VoiceDetail({ id }: { id: string }) {
  const qc = useQueryClient();
  const { has } = useAuth();
  const q = useQuery<{ voice: Voice; locks: Lock[] }>({ queryKey: ["voice", id], queryFn: () => api(`/voices/${id}`) });
  const [busy, setBusy] = useState(false);
  const run = async (fn: () => Promise<unknown>, ok: string) => {
    setBusy(true);
    try { await fn(); toast.success(ok); qc.invalidateQueries({ queryKey: ["voice", id] }); qc.invalidateQueries({ queryKey: ["voices"] }); }
    catch (e) { toast.error(errorMessage(e)); } finally { setBusy(false); }
  };
  return (
    <QueryView q={q}>
      {({ voice: v, locks }) => (
        <div className="space-y-4" data-testid="voice-detail">
          <Card>
            <CardHeader><CardTitle className="flex items-center gap-2"><span className="font-mono text-sm text-slate-500">{v.code}</span>{v.name}<Badge variant={v.status === "LOCKED" ? "green" : "gray"}>{v.status === "LOCKED" ? "Đã khoá" : "Nháp"}</Badge></CardTitle>
              <CardDescription>Voice Lock yêu cầu consent ĐÃ ĐỒNG Ý và có audio tham chiếu.</CardDescription></CardHeader>
            <CardContent>
              {has("character.edit") ? <VoiceForm initial={Object.fromEntries(Object.keys(empty).map((k) => [k, String((v as unknown as Record<string, unknown>)[k] ?? "")])) as F} busy={busy} label="Lưu giọng"
                onSubmit={(f) => run(() => api(`/voices/${v.id}`, { method: "PATCH", body: toBody(f) }), "Đã lưu giọng nói")} /> : <p className="text-sm">{v.accent} · {v.tone}</p>}
            </CardContent>
          </Card>
          <Card>
            <CardHeader><CardTitle className="flex items-center gap-2"><LockIcon className="h-4 w-4" />Voice Lock</CardTitle></CardHeader>
            <CardContent className="space-y-3">
              <Can perm="character.edit"><Button onClick={() => run(() => api(`/voices/${v.id}/locks`, { body: { change_note: "" } }), "Đã tạo Voice Lock nháp")} loading={busy} data-testid="create-voice-lock"><LockIcon />Tạo Voice Lock</Button></Can>
              <LockHistory locks={locks} activeId={v.active_lock_id} canApprove={has("character.lock_approve")} testid="voice-locks"
                onApprove={(lid) => run(() => api(`/voice-locks/${lid}/approve`, { method: "POST" }), "Đã duyệt Voice Lock")} />
            </CardContent>
          </Card>
        </div>
      )}
    </QueryView>
  );
}

export function VoicesTab() {
  const qc = useQueryClient();
  const [sel, setSel] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [busy, setBusy] = useState(false);
  const list = useQuery<Voice[]>({ queryKey: ["voices"], queryFn: () => api("/voices") });
  const create = async (f: F) => {
    setBusy(true);
    try { const v = await api<Voice>("/voices", { body: toBody(f) }); toast.success(`Đã tạo giọng ${v.code}`); setCreating(false); setSel(v.id); qc.invalidateQueries({ queryKey: ["voices"] }); }
    catch (e) { toast.error(errorMessage(e)); } finally { setBusy(false); }
  };
  return (
    <div className="grid gap-4 lg:grid-cols-[320px_1fr]">
      <Card><CardContent className="space-y-2 pt-5">
        <Can perm="character.edit"><Button className="w-full" variant="outline" onClick={() => { setCreating(true); setSel(null); }} data-testid="new-voice"><Plus />Giọng nói mới</Button></Can>
        <QueryView q={list} isEmpty={(d) => !d.length} empty={<EmptyState title="Chưa có giọng nói" />}>
          {(d) => <div className="space-y-1" data-testid="voice-list">{d.map((v) => (
            <button key={v.id} onClick={() => { setSel(v.id); setCreating(false); }} data-testid="voice-item" className={cn("flex w-full items-center justify-between rounded-lg px-3 py-2 text-left text-sm hover:bg-slate-50", sel === v.id && "bg-brand-50")}>
              <span><span className="font-mono text-xs text-slate-500">{v.code}</span><br />{v.name} · {v.accent}</span>
              <Badge variant={v.consent_status === "GRANTED" ? "green" : "yellow"}>{CONSENT[v.consent_status]}</Badge>
            </button>))}</div>}
        </QueryView>
      </CardContent></Card>
      <div>{creating ? <Card><CardHeader><CardTitle>Giọng nói mới</CardTitle></CardHeader><CardContent><VoiceForm initial={empty} busy={busy} label="Tạo giọng nói" onSubmit={create} /></CardContent></Card>
        : sel ? <VoiceDetail id={sel} /> : <EmptyState title="Chọn giọng nói" />}</div>
    </div>
  );
}
