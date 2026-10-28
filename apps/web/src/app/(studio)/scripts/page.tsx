"use client";
import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, FileText, Lightbulb, Pencil, RotateCcw, Save, Sparkles, Wand2 } from "lucide-react";
import { toast } from "sonner";
import { api, errorMessage } from "@/lib/api";
import { useAction } from "@/hooks/use-mutate";
import { PageHeader } from "@/components/app/page-header";
import { RequirePermission, Can } from "@/components/app/require";
import { EmptyState, QueryView } from "@/components/app/states";
import { StatusBadge } from "@/components/app/status-badge";
import { ProjectPicker, useProjectParam } from "@/components/app/project-picker";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Input, Textarea } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { LESSON_STATUS, PROJECT_STATUS, SCENE_STATUS, SEVERITY } from "@/lib/labels";
import { cn, formatDate } from "@/lib/utils";
import type { Lesson, Scene, ScriptView } from "@/types/api";
import { SCENE_KEYS, SceneEditor, toDraft, validateDraft, type SceneDraft } from "@/features/scripts/scene-editor";

const CRIT_LABEL: Record<string, string> = { hook: "Hook", brand_fit: "Hợp thương hiệu", audience_fit: "Hợp khách hàng", feasibility: "Khả thi", compliance: "Tuân thủ" };
const PART_LABEL: [string, string][] = [["scene_type", "1. Loại cảnh"], ["characters", "2. Nhân vật"], ["action", "3. Hành động"], ["setting", "4. Bối cảnh"],
  ["camera", "5. Máy quay"], ["lighting", "6. Ánh sáng"], ["sound", "7. Âm thanh"], ["dialogue", "8. Thoại"], ["negative", "9. Negative Prompt"]];
const EDITABLE = ["CREATED", "SCRIPT_GENERATING", "SCRIPT_REVIEW", "STORYBOARD_READY"];

function Ideas({ v, pid }: { v: ScriptView; pid: string }) {
  const inv = [["script", pid]];
  const ideas = useAction(() => api(`/projects/${pid}/script/ideas`, { method: "POST" }), { success: "AI Script đã tạo 3 ý tưởng", invalidate: inv });
  const select = useAction((i: number) => api(`/projects/${pid}/script/select-idea`, { body: { index: i } }), { success: "Đã chọn ý tưởng", invalidate: inv });
  const write = useAction(() => api(`/projects/${pid}/script/write`, { method: "POST" }), { success: "Đã viết kịch bản & storyboard", invalidate: inv });
  const st = v.project.status;
  const list = v.script?.ideas ?? [];
  return (
    <Card>
      <CardHeader className="flex-row flex-wrap items-center justify-between gap-2">
        <div><CardTitle>Ý tưởng (A02 AI Script)</CardTitle><CardDescription>3 ý tưởng được chấm bằng rubric xác định (hook, thương hiệu, khách hàng, khả thi, tuân thủ).</CardDescription></div>
        <div className="flex gap-2">
          {["CREATED", "SCRIPT_GENERATING", "SCRIPT_REVIEW", "RETRY_PENDING"].includes(st) && (
            <Can perm="script.generate"><Button variant={list.length ? "outline" : "default"} onClick={() => ideas.mutate(undefined)} loading={ideas.isPending} data-testid="gen-ideas"><Lightbulb />{list.length ? "Tạo lại 3 ý tưởng" : "Tạo 3 ý tưởng"}</Button></Can>
          )}
          {st === "SCRIPT_GENERATING" && v.script?.selected_idea_index !== null && v.script?.selected_idea_index !== undefined && (
            <Can perm="script.generate"><Button onClick={() => write.mutate(undefined)} loading={write.isPending} data-testid="write-script"><Wand2 />Viết kịch bản</Button></Can>
          )}
        </div>
      </CardHeader>
      <CardContent>
        {!list.length ? <EmptyState title="Chưa có ý tưởng" description="Bấm 'Tạo 3 ý tưởng' để AI Script đề xuất theo Brand DNA của kênh." /> : (
          <div className="grid gap-3 md:grid-cols-3">
            {list.map((idea) => {
              const selected = v.script?.selected_idea_index === idea.index;
              const crit = idea.compliance_findings.some((f) => f.severity === "CRITICAL");
              return (
                <div key={idea.index} data-testid={`idea-${idea.index}`} className={cn("flex flex-col rounded-xl border p-3", selected ? "border-brand-500 ring-2 ring-brand-200" : "border-slate-200")}>
                  <div className="flex items-start justify-between gap-2">
                    <Badge variant="gray">{idea.angle}</Badge>
                    <span className="text-2xl font-bold text-brand-700" data-testid="idea-score">{idea.score}</span>
                  </div>
                  <p className="mt-2 font-semibold">{idea.title}</p>
                  <p className="mt-1 rounded bg-amber-50 p-2 text-sm italic text-amber-900">Hook 3s: “{idea.hook}”</p>
                  <p className="mt-1 text-xs text-slate-600">{idea.summary}</p>
                  <div className="mt-2 grid grid-cols-2 gap-x-2 text-xs">
                    {Object.entries(idea.scores).map(([k, s]) => <span key={k} className="flex justify-between"><span className="text-slate-500">{CRIT_LABEL[k] ?? k}</span><b>{s}/10</b></span>)}
                  </div>
                  {idea.compliance_findings.length > 0 && (
                    <div className="mt-2 space-y-1" data-testid="idea-compliance">
                      {idea.compliance_findings.map((f, i) => <p key={i} className="text-xs text-red-700"><Badge variant={SEVERITY[f.severity] ?? "gray"}>{f.severity}</Badge> {f.message}</p>)}
                    </div>
                  )}
                  <div className="mt-auto pt-3">
                    {selected ? <Badge variant="green"><CheckCircle2 className="h-3 w-3" />Đã chọn</Badge> : (
                      ["SCRIPT_GENERATING", "SCRIPT_REVIEW"].includes(st) && !crit &&
                      <Can perm="script.edit"><Button size="sm" variant="outline" onClick={() => select.mutate(idea.index)} data-testid={`select-idea-${idea.index}`}>Chọn ý tưởng này</Button></Can>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
        <p className="mt-3 text-[11px] text-slate-400">{list[0]?.scoring_method}</p>
      </CardContent>
    </Card>
  );
}

function ScriptEditor({ v, pid }: { v: ScriptView; pid: string }) {
  const cur = v.current;
  const [editing, setEditing] = useState(false);
  const [hook, setHook] = useState("");
  const [body, setBody] = useState("");
  const [cta, setCta] = useState("");
  const [title, setTitle] = useState("");
  const [note, setNote] = useState("");
  const [scenes, setScenes] = useState<SceneDraft[]>([]);
  const [busy, setBusy] = useState(false);
  const [serverErr, setServerErr] = useState<string | null>(null);
  const qc = useQueryClient();
  const reset = () => {
    setHook(cur?.hook ?? ""); setBody(cur?.body ?? ""); setCta(cur?.cta ?? v.project.cta ?? ""); setTitle(cur?.title ?? v.project.title);
    setScenes(v.scenes.length ? v.scenes.map((s) => toDraft(s as unknown as Record<string, unknown>)) : [toDraft({})]); setNote("");
  };
  useEffect(reset, [cur?.id, v.scenes.length]); // eslint-disable-line react-hooks/exhaustive-deps
  const canEdit = EDITABLE.includes(v.project.status);
  const clientErrors = scenes.flatMap(validateDraft).concat(hook.trim() ? [] : ["Thiếu hook 3 giây"]);
  const save = async () => {
    if (clientErrors.length) { toast.error(clientErrors[0]); return; }
    setBusy(true); setServerErr(null);
    try {
      await api(`/projects/${pid}/script`, { method: "PUT", body: { title, hook, body, cta, note: note || "Chỉnh sửa thủ công", scenes: scenes.map((s) => Object.fromEntries(SCENE_KEYS.map((k) => [k, s[k]]))) } });
      toast.success("Đã lưu phiên bản mới");
      setEditing(false);
      await qc.invalidateQueries({ queryKey: ["script", pid] });
    } catch (e) { setServerErr(errorMessage(e)); toast.error(errorMessage(e)); } finally { setBusy(false); }
  };
  return (
    <Card>
      <CardHeader className="flex-row flex-wrap items-center justify-between gap-2">
        <div>
          <CardTitle>Kịch bản {cur ? `v${cur.version_no}` : ""}</CardTitle>
          <CardDescription>{cur ? `${cur.source === "AGENT" ? "AI Script" : "Chỉnh sửa thủ công"} · ${cur.change_note} · ${formatDate(cur.created_at)}` : "Chưa có kịch bản — tạo bằng AI hoặc viết thủ công."}</CardDescription>
        </div>
        {canEdit && !editing && <Can perm="script.edit"><Button variant="outline" onClick={() => { reset(); setEditing(true); }} data-testid="edit-script"><Pencil />{cur ? "Chỉnh sửa" : "Viết thủ công"}</Button></Can>}
      </CardHeader>
      <CardContent className="space-y-3">
        {!editing && cur && (
          <div className="space-y-2 text-sm">
            <p className="rounded-lg bg-amber-50 p-3"><b>Hook 3 giây:</b> <span data-testid="script-hook">{cur.hook}</span></p>
            <pre className="whitespace-pre-wrap rounded-lg bg-slate-50 p-3 font-sans text-slate-700" data-testid="script-body">{cur.body}</pre>
            <p><b>CTA:</b> {cur.cta}</p>
          </div>
        )}
        {editing && (
          <div className="space-y-3" data-testid="script-form">
            <div className="grid gap-2 md:grid-cols-2">
              <div><Label>Tiêu đề</Label><Input value={title} onChange={(e) => setTitle(e.target.value)} /></div>
              <div><Label>CTA</Label><Input value={cta} onChange={(e) => setCta(e.target.value)} /></div>
            </div>
            <div><Label>Hook 3 giây</Label><Input value={hook} onChange={(e) => setHook(e.target.value)} data-testid="edit-hook" /></div>
            <div><Label>Nội dung</Label><Textarea rows={4} value={body} onChange={(e) => setBody(e.target.value)} /></div>
            <div className="space-y-2">
              {scenes.map((s, i) => <SceneEditor key={i} idx={i} value={s} onChange={(nv) => setScenes(scenes.map((x, j) => (j === i ? nv : x)))} onRemove={scenes.length > 1 ? () => setScenes(scenes.filter((_, j) => j !== i)) : undefined} />)}
              <Button variant="outline" size="sm" onClick={() => setScenes([...scenes, toDraft({ duration_sec: 8 })])} data-testid="add-scene">+ Thêm cảnh</Button>
            </div>
            {clientErrors.length > 0 && <ul className="list-disc rounded-lg bg-red-50 p-3 pl-6 text-sm text-red-700" data-testid="client-errors">{clientErrors.map((e) => <li key={e}>{e}</li>)}</ul>}
            {serverErr && <p className="rounded-lg bg-red-50 p-2 text-sm text-red-700" role="alert">{serverErr}</p>}
            <div className="flex flex-wrap items-end gap-2">
              <div className="flex-1"><Label>Ghi chú phiên bản</Label><Input value={note} onChange={(e) => setNote(e.target.value)} placeholder="Lý do chỉnh sửa" data-testid="version-note" /></div>
              <Button variant="outline" onClick={() => setEditing(false)}>Huỷ</Button>
              <Button onClick={save} loading={busy} disabled={clientErrors.length > 0} data-testid="save-script"><Save />Lưu phiên bản</Button>
            </div>
          </div>
        )}
        {v.check && (v.check.errors.length > 0 || v.check.warnings.length > 0 || v.check.compliance.length > 0) && (
          <div className="space-y-1 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm" data-testid="server-check">
            {v.check.errors.map((e) => <p key={e} className="text-red-700">✗ {e}</p>)}
            {v.check.warnings.map((e) => <p key={e} className="text-amber-800">⚠ {e}</p>)}
            {v.check.compliance.map((f, i) => <p key={i}><Badge variant={SEVERITY[f.severity] ?? "gray"}>{f.severity}</Badge> {f.message} (“{f.match}”)</p>)}
          </div>
        )}
      </CardContent>
    </Card>
  );
}


function Storyboard({ v, pid }: { v: ScriptView; pid: string }) {
  const [edit, setEdit] = useState<string | null>(null);
  const [draft, setDraft] = useState<SceneDraft | null>(null);
  const [busy, setBusy] = useState(false);
  const qc = useQueryClient();
  const rebuild = useAction(() => api(`/projects/${pid}/script/prompts`, { method: "POST" }), { success: "A03 đã tạo lại prompt", invalidate: [["script", pid]] });
  const patch = async (s: Scene) => {
    if (!draft) return;
    const errs = validateDraft(draft, s.order_index);
    if (errs.length) { toast.error(errs[0]); return; }
    setBusy(true);
    try {
      await api(`/scenes/${s.id}`, { method: "PATCH", body: { ...Object.fromEntries(SCENE_KEYS.map((k) => [k, draft[k]])), note: "Sửa cảnh tại M03" } });
      toast.success(`Đã lưu cảnh ${s.order_index + 1}`);
      setEdit(null);
      await qc.invalidateQueries({ queryKey: ["script", pid] });
    } catch (e) { toast.error(errorMessage(e)); } finally { setBusy(false); }
  };
  const approved = !["CREATED", "SCRIPT_GENERATING", "SCRIPT_REVIEW"].includes(v.project.status);
  return (
    <Card>
      <CardHeader className="flex-row flex-wrap items-center justify-between gap-2">
        <div><CardTitle>Storyboard · 9:16 · cảnh 8 giây</CardTitle><CardDescription>Mỗi cảnh 1 hành động chính, tối đa 2 câu thoại. Prompt 9 phần do A03 lắp sau khi duyệt kịch bản.</CardDescription></div>
        {approved && <Can perm="script.edit"><Button variant="outline" onClick={() => rebuild.mutate(undefined)} loading={rebuild.isPending} data-testid="rebuild-prompts"><Sparkles />Tạo lại prompt</Button></Can>}
      </CardHeader>
      <CardContent>
        {!v.scenes.length ? <EmptyState title="Chưa có storyboard" /> : (
          <div className="grid gap-3 lg:grid-cols-2">
            {v.scenes.map((s) => (
              <div key={s.id} className="rounded-xl border border-slate-200 p-3" data-testid={`scene-card-${s.order_index}`}>
                {edit === s.id && draft ? (
                  <div className="space-y-2">
                    <SceneEditor idx={s.order_index} value={draft} onChange={setDraft} />
                    <div className="flex justify-end gap-2">
                      <Button size="sm" variant="outline" onClick={() => setEdit(null)}>Huỷ</Button>
                      <Button size="sm" onClick={() => patch(s)} loading={busy} data-testid={`save-scene-${s.order_index}`}><Save />Lưu cảnh</Button>
                    </div>
                  </div>
                ) : (
                  <>
                    <div className="flex items-center justify-between gap-2">
                      <p className="font-semibold">{s.title || `Cảnh ${s.order_index + 1}`}</p>
                      <div className="flex items-center gap-2">
                        <Badge variant="gray">{s.duration_sec}s · v{s.current_version_no}</Badge>
                        <StatusBadge map={SCENE_STATUS} value={s.status} />
                        {EDITABLE.concat(["ASSET_VALIDATION", "NEEDS_MANUAL_ACTION", "SCENE_QC", "FINAL_QC"]).includes(v.project.status) &&
                          <Can perm="script.edit"><Button size="icon" variant="ghost" aria-label="Sửa cảnh" onClick={() => { setDraft(toDraft(s as unknown as Record<string, unknown>)); setEdit(s.id); }} data-testid={`edit-scene-${s.order_index}`}><Pencil /></Button></Can>}
                      </div>
                    </div>
                    <p className="mt-1 text-sm"><b>Hành động:</b> {s.action}</p>
                    {s.dialogue.map((d, i) => <p key={i} className="text-sm text-slate-700">🗨 <b>{d.speaker}:</b> “{d.text}”</p>)}
                    <p className="mt-1 text-xs text-slate-500">{s.setting} · {s.camera} · {s.lighting}</p>
                    {s.prompt_text && (
                      <details className="mt-2 rounded-lg bg-slate-50 p-2 text-xs" data-testid={`prompt-${s.order_index}`}>
                        <summary className="cursor-pointer font-medium text-brand-700">Prompt 9 phần</summary>
                        <dl className="mt-2 space-y-1">
                          {PART_LABEL.map(([k, l]) => <div key={k}><dt className="font-semibold text-slate-600">{l}</dt><dd className="text-slate-700">{s.prompt_parts?.[k] ?? "—"}</dd></div>)}
                        </dl>
                        <p className="mt-2 font-semibold text-slate-600">Prompt đầy đủ</p>
                        <pre className="whitespace-pre-wrap font-mono text-[11px]">{s.prompt_text}</pre>
                      </details>
                    )}
                  </>
                )}
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function Versions({ v, pid }: { v: ScriptView; pid: string }) {
  const restore = useAction((id: string) => api(`/projects/${pid}/script/versions/${id}/restore`, { method: "POST" }), { success: "Đã khôi phục thành phiên bản mới", invalidate: [["script", pid]] });
  if (!v.versions.length) return <EmptyState title="Chưa có phiên bản" />;
  return (
    <div className="space-y-2" data-testid="versions">
      {v.versions.map((x) => (
        <div key={x.id} className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-slate-200 p-3 text-sm" data-testid="version-row">
          <div>
            <p className="font-medium">v{x.version_no} · {x.title} {x.id === v.script?.current_version_id && <Badge variant="default">Hiện tại</Badge>} {x.id === v.script?.approved_version_id && <Badge variant="green">Đã duyệt</Badge>}</p>
            <p className="text-xs text-slate-500">{x.source === "AGENT" ? "AI Script" : "Thủ công"} · {x.change_note} · {formatDate(x.created_at)} · {x.scenes.length} cảnh</p>
          </div>
          {x.id !== v.script?.current_version_id && EDITABLE.includes(v.project.status) &&
            <Can perm="script.edit"><Button size="sm" variant="outline" onClick={() => restore.mutate(x.id)} data-testid={`restore-${x.version_no}`}><RotateCcw />Khôi phục</Button></Can>}
        </div>
      ))}
    </div>
  );
}

function Approve({ v, pid }: { v: ScriptView; pid: string }) {
  const [comment, setComment] = useState("");
  const approve = useAction(() => api(`/projects/${pid}/script/approve`, { body: { comment } }), { success: "Đã duyệt kịch bản — A03 đã tạo prompt", invalidate: [["script", pid]] });
  if (v.project.status !== "SCRIPT_REVIEW") {
    return v.script?.status === "APPROVED" ? <p className="rounded-lg bg-emerald-50 p-3 text-sm text-emerald-800" data-testid="approved-note">✓ Kịch bản đã được duyệt lúc {formatDate(v.script.approved_at)}</p> : null;
  }
  return (
    <Can perm="script.approve">
      <Card className="border-amber-200">
        <CardContent className="flex flex-wrap items-end gap-2 pt-5">
          <div className="flex-1"><Label>Nhận xét duyệt</Label><Input value={comment} onChange={(e) => setComment(e.target.value)} placeholder="Ví dụ: Đạt chuẩn Brand DNA" data-testid="approve-comment" /></div>
          <Button variant="success" onClick={() => approve.mutate(undefined)} loading={approve.isPending} data-testid="approve-script"><CheckCircle2 />Duyệt kịch bản</Button>
        </CardContent>
      </Card>
    </Can>
  );
}

function Lessons({ pid }: { pid: string }) {
  const q = useQuery<Lesson[]>({ queryKey: ["lessons-for", pid], queryFn: () => api(`/lessons/for-project/${pid}`) });
  if (!q.data?.length) return null;
  return (
    <Card>
      <CardHeader><CardTitle className="text-sm">Bài học liên quan (A09)</CardTitle></CardHeader>
      <CardContent className="space-y-2 text-sm">
        {q.data.map((l) => <p key={l.id}><StatusBadge map={LESSON_STATUS} value={l.status} /> <b>{l.code}</b> {l.title}</p>)}
      </CardContent>
    </Card>
  );
}

export default function ScriptsPage() {
  const [pid, setPid] = useProjectParam();
  const q = useQuery<ScriptView>({ queryKey: ["script", pid], queryFn: () => api(`/projects/${pid}/script`), enabled: !!pid });
  return (
    <RequirePermission perm="project.view">
      <PageHeader code="M03" title="AI Script & Storyboard" description="Ý tưởng → hook 3 giây → kịch bản → storyboard 8 giây/cảnh → prompt 9 phần → duyệt. Video dọc 9:16."
        actions={<ProjectPicker value={pid} onChange={setPid} />} />
      {!pid ? <EmptyState title="Chọn dự án" description="Chọn một dự án để làm việc với kịch bản." /> : (
        <QueryView q={q}>
          {(v) => (
            <div className="space-y-4">
              <div className="flex flex-wrap items-center gap-2 text-sm" data-testid="script-status">
                <FileText className="h-4 w-4 text-slate-400" /><b>{v.project.code}</b> {v.project.title}
                <StatusBadge map={PROJECT_STATUS} value={v.project.status} />
                <Badge variant="gray">{v.project.aspect_ratio} · {v.project.duration_sec}s</Badge>
              </div>
              <Approve v={v} pid={pid} />
              <Tabs defaultValue="script">
                <TabsList>
                  <TabsTrigger value="script">Kịch bản & storyboard</TabsTrigger>
                  <TabsTrigger value="ideas" data-testid="tab-ideas">Ý tưởng</TabsTrigger>
                  <TabsTrigger value="versions" data-testid="tab-versions">Phiên bản ({v.versions.length})</TabsTrigger>
                </TabsList>
                <TabsContent value="script" className="space-y-4">
                  {!v.current && <Ideas v={v} pid={pid} />}
                  <ScriptEditor v={v} pid={pid} />
                  <Storyboard v={v} pid={pid} />
                </TabsContent>
                <TabsContent value="ideas"><Ideas v={v} pid={pid} /></TabsContent>
                <TabsContent value="versions"><Versions v={v} pid={pid} /></TabsContent>
              </Tabs>
              <Lessons pid={pid} />
            </div>
          )}
        </QueryView>
      )}
    </RequirePermission>
  );
}
