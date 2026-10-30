"use client";
import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { History, Plus, Save } from "lucide-react";
import { api } from "@/lib/api";
import { useAction } from "@/hooks/use-mutate";
import { useAuth } from "@/hooks/use-auth";
import { PageHeader } from "@/components/app/page-header";
import { RequirePermission, Can } from "@/components/app/require";
import { QueryView } from "@/components/app/states";
import { Field } from "@/components/app/field";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Textarea } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { PLATFORMS } from "@/lib/labels";
import { cn, formatDate } from "@/lib/utils";
import { FacebookConnect, type FbTarget } from "@/features/channels/facebook-connect";

type Brand = {
  slogan: string; brand_promise: string; big_idea: string; brand_voice: string[]; audience: string; content_pillars: string[];
  character_set: string[]; voice_set: string[]; scene_set: string[]; cta_rules: string[]; quality_rules: string[];
  publishing_rules: string[]; forbidden_terms: string[]; version_no: number; updated_at: string | null;
  history: { version: number; at: string; by: string; note: string; data: Record<string, unknown> }[];
};
type Channel = { id: string; code: string; name: string; description: string; platforms: string[]; is_active: boolean; project_count: number; brand: Brand | null;
  publish_targets?: { FACEBOOK?: FbTarget } };

const TEXT_FIELDS: [keyof Brand, string][] = [["slogan", "Slogan"], ["brand_promise", "Brand Promise"], ["big_idea", "Big Idea"]];
const LIST_FIELDS: [keyof Brand, string, string][] = [
  ["brand_voice", "Brand Voice", "Mỗi dòng một tính từ"], ["content_pillars", "Content Pillars", "Mỗi dòng một trụ cột"],
  ["character_set", "Character Set", "Mã nhân vật, mỗi dòng một mã"], ["voice_set", "Voice Set", "Mã giọng"],
  ["scene_set", "Scene Set", "Mã Scene Lock"], ["cta_rules", "CTA Rules", "Mỗi dòng một quy tắc"],
  ["quality_rules", "Quality Rules", ""], ["publishing_rules", "Publishing Rules", ""],
  ["forbidden_terms", "Từ / tuyên bố cấm", "Bộ lọc tuân thủ dùng danh sách này"],
];
const toLines = (a?: string[]) => (a ?? []).join("\n");
const fromLines = (s: string) => s.split("\n").map((x) => x.trim()).filter(Boolean);

function BrandEditor({ ch, canEdit }: { ch: Channel; canEdit: boolean }) {
  const b = ch.brand;
  const [form, setForm] = useState<Record<string, string>>({});
  const [note, setNote] = useState("");
  useEffect(() => {
    const f: Record<string, string> = { audience: b?.audience ?? "" };
    TEXT_FIELDS.forEach(([k]) => (f[k] = (b?.[k] as string) ?? ""));
    LIST_FIELDS.forEach(([k]) => (f[k] = toLines(b?.[k] as string[])));
    setForm(f);
    setNote("");
  }, [b, ch.id]);
  const save = useAction(() => {
    const body: Record<string, unknown> = { change_note: note, audience: form.audience };
    TEXT_FIELDS.forEach(([k]) => (body[k] = form[k]));
    LIST_FIELDS.forEach(([k]) => (body[k] = fromLines(form[k] ?? "")));
    return api(`/channels/${ch.id}/brand`, { method: "PUT", body });
  }, { success: "Đã lưu Brand DNA (phiên bản mới)", invalidate: [["channels-full"]] });
  const set = (k: string, v: string) => setForm((f) => ({ ...f, [k]: v }));
  return (
    <div className="space-y-3" data-testid="brand-editor">
      <div className="grid gap-3 md:grid-cols-3">
        {TEXT_FIELDS.map(([k, l]) => (
          <Field key={k} label={l}><Input value={form[k] ?? ""} onChange={(e) => set(k, e.target.value)} disabled={!canEdit} data-testid={`brand-${k}`} /></Field>
        ))}
      </div>
      <Field label="Audience"><Textarea value={form.audience ?? ""} onChange={(e) => set("audience", e.target.value)} disabled={!canEdit} data-testid="brand-audience" /></Field>
      <div className="grid gap-3 md:grid-cols-3">
        {LIST_FIELDS.map(([k, l, h]) => (
          <Field key={k} label={l} hint={h}>
            <Textarea rows={4} value={form[k] ?? ""} onChange={(e) => set(k, e.target.value)} disabled={!canEdit} data-testid={`brand-${k}`} />
          </Field>
        ))}
      </div>
      {canEdit && (
        <div className="flex flex-wrap items-end gap-2">
          <Field label="Ghi chú thay đổi" className="min-w-64 flex-1 space-y-1"><Input value={note} onChange={(e) => setNote(e.target.value)} data-testid="brand-note" /></Field>
          <Button onClick={() => save.mutate(undefined)} loading={save.isPending} data-testid="brand-save"><Save />Lưu phiên bản mới</Button>
        </div>
      )}
    </div>
  );
}

function NewChannel() {
  const [open, setOpen] = useState(false);
  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const [desc, setDesc] = useState("");
  const [platforms, setPlatforms] = useState<string[]>(["FACEBOOK"]);
  const create = useAction(() => api("/channels", { body: { code, name, description: desc, platforms } }),
    { success: "Đã tạo kênh", invalidate: [["channels-full"], ["channels-mini"]], onSuccess: () => { setOpen(false); setCode(""); setName(""); setDesc(""); } });
  const codeOk = /^[A-Z0-9_]{2,40}$/.test(code);
  return (
    <>
      <Button onClick={() => setOpen(true)} data-testid="new-channel"><Plus />Tạo kênh</Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader><DialogTitle>Tạo kênh mới</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <Field label="Mã kênh (IN HOA, số, _)" error={code && !codeOk ? "Chỉ gồm A-Z, 0-9, _ (2–40 ký tự)" : undefined}>
              <Input value={code} onChange={(e) => setCode(e.target.value.toUpperCase())} data-testid="ch-code" />
            </Field>
            <Field label="Tên kênh"><Input value={name} onChange={(e) => setName(e.target.value)} data-testid="ch-name" /></Field>
            <Field label="Mô tả"><Textarea value={desc} onChange={(e) => setDesc(e.target.value)} /></Field>
            <div className="flex flex-wrap gap-3">
              {PLATFORMS.map((p) => (
                <label key={p} className="flex items-center gap-1 text-sm">
                  <input type="checkbox" checked={platforms.includes(p)} onChange={() => setPlatforms((x) => (x.includes(p) ? x.filter((y) => y !== p) : [...x, p]))} />{p}
                </label>
              ))}
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)}>Huỷ</Button>
            <Button disabled={!codeOk || name.trim().length < 2} loading={create.isPending} onClick={() => create.mutate(undefined)} data-testid="ch-create">Tạo</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

export default function ChannelsPage() {
  const { has } = useAuth();
  const q = useQuery<Channel[]>({ queryKey: ["channels-full"], queryFn: () => api("/channels") });
  const [sel, setSel] = useState<string | null>(null);
  const [showHist, setShowHist] = useState(false);
  const patch = useAction((v: { id: string; body: Record<string, unknown> }) => api(`/channels/${v.id}`, { method: "PATCH", body: v.body }),
    { success: "Đã cập nhật kênh", invalidate: [["channels-full"], ["channels-mini"]] });
  return (
    <RequirePermission perm="channel.view">
      <PageHeader code="M13" title="Quản lý kênh & Brand DNA" description="Mỗi kênh có Brand DNA riêng; mọi thay đổi tạo phiên bản mới và lưu lịch sử."
        actions={<Can perm="channel.edit"><NewChannel /></Can>} />
      <QueryView q={q}>
        {(list) => {
          const ch = list.find((c) => c.id === sel) ?? list[0];
          return (
            <div className="grid gap-4 lg:grid-cols-4">
              <div className="space-y-2" data-testid="channel-list">
                {list.map((c) => (
                  <button key={c.id} onClick={() => setSel(c.id)} data-testid="channel-item"
                    className={cn("w-full rounded-xl border bg-white p-3 text-left shadow-sm transition", c.id === ch?.id ? "border-brand-500 ring-2 ring-brand-100" : "border-slate-200 hover:border-brand-300")}>
                    <div className="flex items-center justify-between"><p className="font-semibold">{c.name}</p>{!c.is_active && <Badge variant="gray">Ngừng</Badge>}</div>
                    <p className="text-xs text-slate-500">{c.code} · {c.project_count} dự án · DNA v{c.brand?.version_no ?? 1}</p>
                    <div className="mt-1 flex flex-wrap gap-1">{c.platforms.map((p) => <Badge key={p} variant={p === "FACEBOOK" && c.publish_targets?.FACEBOOK ? "green" : "gray"}>{p}</Badge>)}</div>
                  </button>
                ))}
              </div>
              {ch && (
                <Card className="lg:col-span-3">
                  <CardHeader className="flex-row flex-wrap items-center justify-between gap-2">
                    <div>
                      <CardTitle data-testid="channel-name">{ch.name}</CardTitle>
                      <p className="text-sm text-slate-500">{ch.description}</p>
                    </div>
                    <div className="flex flex-wrap items-center gap-3">
                      <Can perm="channel.edit">
                        <div className="flex flex-wrap gap-2">
                          {PLATFORMS.map((p) => (
                            <label key={p} className="flex items-center gap-1 text-xs">
                              <input type="checkbox" checked={ch.platforms.includes(p)} data-testid={`platform-${p}`}
                                onChange={() => patch.mutate({ id: ch.id, body: { platforms: ch.platforms.includes(p) ? ch.platforms.filter((x) => x !== p) : [...ch.platforms, p] } })} />{p}
                            </label>
                          ))}
                        </div>
                        <label className="flex items-center gap-2 text-sm">Hoạt động
                          <Switch checked={ch.is_active} onCheckedChange={(v) => patch.mutate({ id: ch.id, body: { is_active: v } })} data-testid="channel-active" />
                        </label>
                      </Can>
                      <Button variant="outline" size="sm" onClick={() => setShowHist((s) => !s)} data-testid="brand-history-toggle"><History />Lịch sử ({ch.brand?.history.length ?? 0})</Button>
                    </div>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    {showHist && (
                      <div className="rounded-lg border border-slate-200 p-3" data-testid="brand-history">
                        {(ch.brand?.history ?? []).length === 0 && <p className="text-sm text-slate-500">Chưa có thay đổi</p>}
                        {[...(ch.brand?.history ?? [])].reverse().map((h, i) => (
                          <details key={i} className="border-b border-slate-100 py-1 text-sm last:border-0">
                            <summary className="cursor-pointer">v{h.version} · {formatDate(h.at)} · {h.by} {h.note && `— ${h.note}`}</summary>
                            <pre className="mt-1 max-h-60 overflow-auto rounded bg-slate-50 p-2 text-xs">{JSON.stringify(h.data, null, 2)}</pre>
                          </details>
                        ))}
                      </div>
                    )}
                    <FacebookConnect channelId={ch.id} target={ch.publish_targets?.FACEBOOK} canEdit={has("channel.edit")} />
                    <p className="text-xs text-slate-500">Brand DNA phiên bản v{ch.brand?.version_no ?? 1}{ch.brand?.updated_at ? ` · cập nhật ${formatDate(ch.brand.updated_at)}` : ""}</p>
                    <BrandEditor ch={ch} canEdit={has("channel.edit")} />
                  </CardContent>
                </Card>
              )}
            </div>
          );
        }}
      </QueryView>
    </RequirePermission>
  );
}
