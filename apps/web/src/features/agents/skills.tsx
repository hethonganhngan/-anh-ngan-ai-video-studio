"use client";
import { useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { FileUp, Pencil, Plus, Trash2 } from "lucide-react";
import { api } from "@/lib/api";
import { useAction } from "@/hooks/use-mutate";
import { useAuth } from "@/hooks/use-auth";
import { EmptyState, QueryView } from "@/components/app/states";
import { Field } from "@/components/app/field";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Textarea } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { formatDate, formatNumber } from "@/lib/utils";

export type Skill = {
  id: string; code: string; name: string; description: string; content: string; agent_codes: string[];
  is_enabled: boolean; source: string; sort_order: number; chars: number; updated_at: string | null;
};
type LlmAgent = { code: string; name: string };

function SkillDialog({ skill, agents, onClose }: { skill: Skill | null; agents: LlmAgent[]; onClose: () => void }) {
  const [f, setF] = useState({
    name: skill?.name ?? "", description: skill?.description ?? "", content: skill?.content ?? "",
    agent_codes: skill?.agent_codes ?? [], sort_order: skill?.sort_order ?? 100,
  });
  const save = useAction(() => skill
    ? api(`/agents/skills/${skill.id}`, { method: "PATCH", body: f })
    : api("/agents/skills", { body: f }),
  { success: skill ? "Đã lưu skill" : "Đã thêm skill", invalidate: [["agent-skills"]], onSuccess: onClose });
  const toggleAgent = (code: string) => setF((x) => ({
    ...x, agent_codes: x.agent_codes.includes(code) ? x.agent_codes.filter((c) => c !== code) : [...x.agent_codes, code],
  }));
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent wide>
        <DialogHeader><DialogTitle>{skill ? `Sửa skill — ${skill.name}` : "Thêm skill"}</DialogTitle></DialogHeader>
        <div className="grid gap-3 md:grid-cols-2">
          <Field label="Tên skill *"><Input value={f.name} onChange={(e) => setF((x) => ({ ...x, name: e.target.value }))} data-testid="skill-name" /></Field>
          <Field label="Thứ tự ưu tiên (nhỏ trước)"><Input type="number" min={0} value={f.sort_order} onChange={(e) => setF((x) => ({ ...x, sort_order: Number(e.target.value) }))} data-testid="skill-order" /></Field>
          <div className="md:col-span-2"><Field label="Mô tả ngắn"><Input value={f.description} onChange={(e) => setF((x) => ({ ...x, description: e.target.value }))} data-testid="skill-desc" /></Field></div>
          <div className="md:col-span-2">
            <Field label={`Nội dung hướng dẫn * (${formatNumber(f.content.length)} / 60.000 ký tự)`} hint="Viết như SKILL.md: quy tắc, giọng thương hiệu, điều cấm, ví dụ mẫu. Agent đọc nội dung này trước mỗi lần chạy.">
              <Textarea rows={14} className="font-mono text-xs" value={f.content} onChange={(e) => setF((x) => ({ ...x, content: e.target.value }))} data-testid="skill-content" />
            </Field>
          </div>
          <div className="md:col-span-2">
            <p className="text-sm font-medium">Cắm vào Agent</p>
            <div className="mt-1 flex flex-wrap gap-2" data-testid="skill-agents">
              {agents.map((a) => (
                <label key={a.code} className="flex items-center gap-1.5 rounded-md border px-2 py-1 text-sm">
                  <input type="checkbox" checked={f.agent_codes.includes(a.code)} onChange={() => toggleAgent(a.code)} data-testid={`skill-agent-${a.code}`} />
                  {a.code} · {a.name}
                </label>
              ))}
            </div>
            <p className="mt-1 text-[11px] text-slate-500">Chỉ agent dùng LLM nhận skill. Agent rule-engine (phép tính xác định) không đọc hướng dẫn.</p>
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Huỷ</Button>
          <Button disabled={f.name.trim().length < 2 || f.content.trim().length < 10} loading={save.isPending} onClick={() => save.mutate(undefined)} data-testid="skill-save">Lưu</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export function SkillsCard({ agents }: { agents: LlmAgent[] }) {
  const { has } = useAuth();
  const manage = has("agent.manage");
  const q = useQuery<Skill[]>({ queryKey: ["agent-skills"], queryFn: () => api("/agents/skills") });
  const [edit, setEdit] = useState<Skill | "new" | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const toggle = useAction((v: { id: string; on: boolean }) => api(`/agents/skills/${v.id}`, { method: "PATCH", body: { is_enabled: v.on } }),
    { success: "Đã cập nhật skill", invalidate: [["agent-skills"]] });
  const remove = useAction((id: string) => api(`/agents/skills/${id}`, { method: "DELETE" }), { success: "Đã xoá skill", invalidate: [["agent-skills"]] });
  const upload = useAction((file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    fd.append("agent_codes", agents.map((a) => a.code).join(","));
    return api<Skill>("/agents/skills/import", { form: fd });
  }, { success: (s) => `Đã nạp skill “${s.name}” — cắm sẵn vào mọi agent dùng LLM`, invalidate: [["agent-skills"]] });
  const names = Object.fromEntries(agents.map((a) => [a.code, a.name]));
  return (
    <Card className="mb-4" data-testid="skills-card">
      <CardHeader className="flex-row flex-wrap items-center justify-between gap-2">
        <div>
          <CardTitle>Skills của Agent</CardTitle>
          <p className="text-sm text-slate-500">Gói hướng dẫn (SKILL.md) cắm vào agent dùng LLM. Skill đang bật được ghép vào lời dặn của agent trước mỗi lần chạy; tắt là ngừng dùng ngay.</p>
        </div>
        {manage && (
          <div className="flex gap-2">
            <input ref={fileRef} type="file" accept=".md,.markdown,.txt,text/markdown,text/plain" className="hidden" data-testid="skill-file"
              onChange={(e) => { const f = e.target.files?.[0]; if (f) upload.mutate(f); e.target.value = ""; }} />
            <Button variant="outline" loading={upload.isPending} onClick={() => fileRef.current?.click()} data-testid="skill-import"><FileUp />Nạp file SKILL.md</Button>
            <Button onClick={() => setEdit("new")} data-testid="skill-add"><Plus />Thêm skill</Button>
          </div>
        )}
      </CardHeader>
      <CardContent>
        <QueryView q={q} isEmpty={(d) => d.length === 0} empty={<EmptyState title="Chưa có skill nào" description="Nạp file SKILL.md (ví dụ DNA thương hiệu Ánh Ngân, quy tắc marketing) rồi cắm vào A02 AI Script." />}>
          {(skills) => (
            <div className="divide-y" data-testid="skills-list">
              {skills.map((s) => (
                <div key={s.id} className="flex flex-wrap items-start gap-3 py-3" data-testid={`skill-${s.code}`}>
                  <Switch checked={s.is_enabled} disabled={!manage} onCheckedChange={(on) => toggle.mutate({ id: s.id, on })} aria-label={`Bật skill ${s.name}`} data-testid={`skill-toggle-${s.code}`} />
                  <div className="min-w-0 flex-1">
                    <p className="font-medium">{s.name} {!s.is_enabled && <Badge variant="gray">Đang tắt</Badge>}</p>
                    {s.description && <p className="text-sm text-slate-600">{s.description}</p>}
                    <div className="mt-1 flex flex-wrap items-center gap-1">
                      {s.agent_codes.length ? s.agent_codes.map((c) => <Badge key={c} variant="purple">{c} · {names[c] ?? c}</Badge>) : <Badge variant="yellow">Chưa cắm vào agent nào</Badge>}
                      <span className="text-[11px] text-slate-400">{formatNumber(s.chars)} ký tự · {s.source === "UPLOAD" ? "nạp từ file" : "nhập tay"}{s.updated_at ? ` · ${formatDate(s.updated_at)}` : ""}</span>
                    </div>
                  </div>
                  {manage && (
                    <div className="flex gap-1">
                      <Button size="sm" variant="ghost" onClick={() => setEdit(s)} data-testid={`skill-edit-${s.code}`}><Pencil />Sửa</Button>
                      <Button size="sm" variant="ghost" onClick={() => { if (window.confirm(`Xoá skill “${s.name}”?`)) remove.mutate(s.id); }} data-testid={`skill-delete-${s.code}`}><Trash2 />Xoá</Button>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </QueryView>
      </CardContent>
      {edit && <SkillDialog skill={edit === "new" ? null : edit} agents={agents} onClose={() => setEdit(null)} />}
    </Card>
  );
}
