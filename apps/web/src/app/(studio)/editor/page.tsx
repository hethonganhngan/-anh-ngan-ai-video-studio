"use client";
import { useEffect, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowDown, ArrowUp, Download, Mic, Music, PlayCircle, Plus, RotateCcw, Save, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { api, assetUrl, errorMessage } from "@/lib/api";
import { PageHeader } from "@/components/app/page-header";
import { RequirePermission, Can } from "@/components/app/require";
import { EmptyState, QueryView } from "@/components/app/states";
import { StatusBadge } from "@/components/app/status-badge";
import { ProjectPicker, useProjectParam } from "@/components/app/project-picker";
import { AssetUploader } from "@/components/app/asset-uploader";
import { AssetImage, VideoPlayer } from "@/components/app/media";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, NativeSelect } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { useAuth } from "@/hooks/use-auth";
import { JOB_STATUS, PROJECT_STATUS } from "@/lib/labels";
import { formatBytes, formatDate } from "@/lib/utils";
import type { Asset, GenerationJob, Page, Project, Scene } from "@/types/api";
import { normalize, validateTimeline, type RenderJob, type RenderOut, type Timeline } from "@/features/editor/types";

type Row = { scene: Scene; jobs: GenerationJob[]; outputs: Asset[] };
const EDITABLE = ["SCENE_QC", "FINAL_QC", "RENDERING", "GENERATING", "NEEDS_MANUAL_ACTION", "APPROVAL_PENDING"];
const RENDERABLE = ["SCENE_QC", "FINAL_QC", "RETRY_PENDING", "APPROVAL_PENDING"];
const POS: Record<string, string> = { top_right: "Trên phải", top_left: "Trên trái", bottom_right: "Dưới phải", bottom_left: "Dưới trái" };
const num = (v: string, d = 0) => (v === "" || Number.isNaN(Number(v)) ? d : Number(v));

function Editor({ project }: { project: Project }) {
  const pid = project.id;
  const qc = useQueryClient();
  const { has } = useAuth();
  const tlq = useQuery<Timeline>({ queryKey: ["timeline", pid], queryFn: () => api(`/projects/${pid}/timeline`) });
  const rows = useQuery<Row[]>({ queryKey: ["production", pid], queryFn: () => api(`/projects/${pid}/production`) });
  const audios = useQuery<Page<Asset>>({ queryKey: ["assets", "AUDIO"], queryFn: () => api("/assets?asset_type=AUDIO&page_size=200") });
  const logos = useQuery<Page<Asset>>({ queryKey: ["assets", "LOGO"], queryFn: () => api("/assets?asset_type=LOGO&page_size=200") });
  const renders = useQuery<RenderOut[]>({ queryKey: ["renders", pid], queryFn: () => api(`/projects/${pid}/renders`), refetchInterval: project.status === "RENDERING" ? 3000 : false });
  const jobs = useQuery<RenderJob[]>({ queryKey: ["render-jobs", pid], queryFn: () => api(`/render-jobs?project_id=${pid}`),
    refetchInterval: (q) => ((q.state.data ?? []).some((j) => ["QUEUED", "RUNNING"].includes(j.status)) ? 3000 : false) });
  const [tl, setTl] = useState<Timeline | null>(null);
  const [dirty, setDirty] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  useEffect(() => { if (tlq.data && !dirty) setTl(normalize(tlq.data)); }, [tlq.data, dirty]);

  const sceneById = useMemo(() => Object.fromEntries((rows.data ?? []).map((r) => [r.scene.id, r])), [rows.data]);
  const durations = useMemo(() => {
    const d: Record<string, number> = {};
    (rows.data ?? []).forEach((r) => r.outputs.forEach((a) => { if (a.duration_sec) d[a.id] = a.duration_sec; }));
    return d;
  }, [rows.data]);
  if (!tl) return <QueryView q={tlq}>{() => null}</QueryView>;

  const update = (fn: (t: Timeline) => Timeline) => { setTl(fn(tl)); setDirty(true); };
  const errors = validateTimeline(tl, durations);
  const total = tl.clips.reduce((s, c) => s + ((c.trim_end ?? (c.asset_id ? durations[c.asset_id] ?? 8 : 8)) - c.trim_start), 0);
  const canEdit = has("editor.edit") && EDITABLE.includes(project.status);
  const move = (i: number, dir: -1 | 1) => update((t) => { const c = [...t.clips]; const j = i + dir; if (j < 0 || j >= c.length) return t; [c[i], c[j]] = [c[j], c[i]]; return { ...t, clips: c }; });
  const invalidate = () => { ["timeline", "renders", "render-jobs", "project"].forEach((k) => qc.invalidateQueries({ queryKey: [k, pid] })); };

  const save = async () => {
    if (errors.length) { toast.error(errors[0]); return false; }
    setBusy("save");
    try { await api(`/projects/${pid}/timeline`, { method: "PUT", body: tl }); toast.success("Đã lưu timeline"); setDirty(false); invalidate(); return true; }
    catch (e) { toast.error(errorMessage(e)); return false; } finally { setBusy(null); }
  };
  const reset = async () => {
    setBusy("reset");
    try { const t = await api<Timeline>(`/projects/${pid}/timeline/reset`, { method: "POST" }); setTl(normalize(t)); setDirty(false); toast.success("Đã đặt lại timeline mặc định"); invalidate(); }
    catch (e) { toast.error(errorMessage(e)); } finally { setBusy(null); }
  };
  const exportMp4 = async () => {
    if (dirty && canEdit && !(await save())) return;
    setBusy("render");
    try { await api(`/projects/${pid}/render`, { method: "POST" }); toast.success("Đã gửi render MP4"); invalidate(); }
    catch (e) { toast.error(errorMessage(e)); } finally { setBusy(null); }
  };
  const genVoiceover = async () => {
    if (dirty && !(await save())) return;
    setBusy("tts");
    try {
      const r = await api<{ timeline: Timeline; duration_sec: number; cost_vnd: number; simulated: boolean; warnings: string[] }>(
        `/projects/${pid}/voiceover/generate`, { method: "POST", body: {} });
      setTl(normalize(r.timeline)); setDirty(false);
      toast.success(`Đã tạo giọng đọc ${r.duration_sec.toFixed(1)}s${r.simulated ? " (DEMO — tiếng bíp mô phỏng)" : ` · ${r.cost_vnd.toLocaleString("vi-VN")} đ`}`);
      r.warnings.forEach((w) => toast.warning(w));
      invalidate(); qc.invalidateQueries({ queryKey: ["assets", "AUDIO"] });
    } catch (e) { toast.error(errorMessage(e)); } finally { setBusy(null); }
  };
  const audioOpts = audios.data?.items ?? [];
  const logoOpts = logos.data?.items ?? [];

  return (
    <div className="space-y-4">
      <Card>
        <CardContent className="flex flex-wrap items-center gap-3 pt-5">
          <b>{project.code}</b><StatusBadge map={PROJECT_STATUS} value={project.status} />
          <Badge variant="gray" data-testid="timeline-total">Tổng ≈ {total.toFixed(1)}s · 9:16 · 1080x1920</Badge>
          {dirty && <Badge variant="yellow">Chưa lưu</Badge>}
          <div className="ml-auto flex flex-wrap gap-2">
            {canEdit && <Button variant="outline" onClick={reset} loading={busy === "reset"} data-testid="reset-timeline"><RotateCcw />Đặt lại mặc định</Button>}
            {canEdit && <Button variant="outline" onClick={save} loading={busy === "save"} disabled={!dirty} data-testid="save-timeline"><Save />Lưu timeline</Button>}
            <Can perm="render.run"><Button onClick={exportMp4} loading={busy === "render"} disabled={!RENDERABLE.includes(project.status) || errors.length > 0} data-testid="export-mp4"><PlayCircle />Export MP4</Button></Can>
          </div>
        </CardContent>
      </Card>
      {errors.length > 0 && <ul className="list-disc rounded-lg bg-red-50 p-3 pl-6 text-sm text-red-700" data-testid="timeline-errors">{errors.map((e) => <li key={e}>{e}</li>)}</ul>}

      <div className="grid gap-4 xl:grid-cols-[1fr_360px]">
        <div className="space-y-4">
          <Card>
            <CardHeader><CardTitle>Timeline video</CardTitle><CardDescription>Sắp xếp cảnh, cắt đoạn (giây) và chỉnh âm lượng từng clip.</CardDescription></CardHeader>
            <CardContent className="space-y-2" data-testid="timeline-clips">
              <div className="flex h-8 overflow-hidden rounded-md bg-slate-100">
                {tl.clips.map((c, i) => {
                  const len = (c.trim_end ?? (c.asset_id ? durations[c.asset_id] ?? 8 : 8)) - c.trim_start;
                  return <div key={i} className="flex items-center justify-center border-r border-white bg-brand-500 text-[10px] text-white" style={{ width: `${(len / Math.max(total, 1)) * 100}%` }}>#{(sceneById[c.scene_id]?.scene.order_index ?? i) + 1}</div>;
                })}
              </div>
              {tl.clips.map((c, i) => {
                const row = sceneById[c.scene_id];
                const dur = c.asset_id ? durations[c.asset_id] : undefined;
                return (
                  <div key={`${c.scene_id}-${i}`} className="grid items-end gap-2 rounded-lg border border-slate-200 p-2 md:grid-cols-[auto_1fr_90px_90px_80px_auto]" data-testid={`clip-${i}`}>
                    <div className="flex flex-col">
                      <Button size="icon" variant="ghost" disabled={!canEdit || i === 0} onClick={() => move(i, -1)} aria-label="Lên" data-testid={`clip-up-${i}`}><ArrowUp /></Button>
                      <Button size="icon" variant="ghost" disabled={!canEdit || i === tl.clips.length - 1} onClick={() => move(i, 1)} aria-label="Xuống" data-testid={`clip-down-${i}`}><ArrowDown /></Button>
                    </div>
                    <div className="text-sm">
                      <p className="font-medium" data-testid={`clip-title-${i}`}>Cảnh {(row?.scene.order_index ?? 0) + 1}: {row?.scene.title}</p>
                      <NativeSelect className="mt-1" disabled={!canEdit} value={c.asset_id ?? ""} onChange={(e) => update((t) => ({ ...t, clips: t.clips.map((x, j) => (j === i ? { ...x, asset_id: e.target.value || null, trim_end: null } : x)) }))}>
                        <option value="">— chọn video —</option>
                        {(row?.outputs ?? []).map((a, k) => <option key={a.id} value={a.id}>Bản #{(row?.outputs.length ?? 0) - k} · {a.source} · {a.duration_sec?.toFixed(1)}s</option>)}
                      </NativeSelect>
                      <p className="text-[11px] text-slate-500">Thời lượng clip: {dur ? `${dur.toFixed(1)}s` : "—"}</p>
                    </div>
                    <div><Label className="text-xs">Đầu (s)</Label><Input type="number" step="0.1" min={0} disabled={!canEdit} value={c.trim_start} data-testid={`trim-start-${i}`}
                      onChange={(e) => update((t) => ({ ...t, clips: t.clips.map((x, j) => (j === i ? { ...x, trim_start: num(e.target.value) } : x)) }))} /></div>
                    <div><Label className="text-xs">Cuối (s)</Label><Input type="number" step="0.1" min={0} disabled={!canEdit} value={c.trim_end ?? ""} placeholder={dur ? dur.toFixed(1) : "hết"} data-testid={`trim-end-${i}`}
                      onChange={(e) => update((t) => ({ ...t, clips: t.clips.map((x, j) => (j === i ? { ...x, trim_end: e.target.value === "" ? null : num(e.target.value) } : x)) }))} /></div>
                    <div><Label className="text-xs">Âm lượng</Label><Input type="number" step="0.1" min={0} max={2} disabled={!canEdit} value={c.volume}
                      onChange={(e) => update((t) => ({ ...t, clips: t.clips.map((x, j) => (j === i ? { ...x, volume: num(e.target.value, 1) } : x)) }))} /></div>
                    <div className="w-16"><VideoPlayer assetId={c.asset_id} className="max-h-24" /></div>
                  </div>
                );
              })}
            </CardContent>
          </Card>

          <Card>
            <CardHeader><CardTitle className="flex items-center gap-2"><Music className="h-4 w-4" />Audio tracks</CardTitle><CardDescription>Voice-over (giọng AI hoặc file thu âm có consent) và nhạc nền. Âm thanh được chuẩn hoá loudness khi render.</CardDescription></CardHeader>
            <CardContent className="space-y-3">
              <div className="space-y-2" data-testid="voiceovers">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="text-sm font-medium">Voice-over</p>
                  {canEdit && <Button size="sm" onClick={genVoiceover} loading={busy === "tts"} data-testid="generate-voiceover"><Mic />Tạo giọng đọc AI</Button>}
                </div>
                {canEdit && <p className="text-[11px] text-slate-500">Đọc lời thoại các cảnh bằng Voice Profile của dự án, đặt đúng mốc từng cảnh và giảm âm lượng cảnh còn 35%. Tạo lại sẽ thay bản cũ.</p>}
                {tl.voiceover.map((v, i) => (
                  <div key={i} className="grid items-end gap-2 md:grid-cols-[1fr_100px_100px_auto]">
                    <NativeSelect disabled={!canEdit} value={v.asset_id} onChange={(e) => update((t) => ({ ...t, voiceover: t.voiceover.map((x, j) => (j === i ? { ...x, asset_id: e.target.value } : x)) }))} data-testid={`vo-asset-${i}`}>
                      <option value="">— chọn audio —</option>{audioOpts.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
                    </NativeSelect>
                    <div><Label className="text-xs">Bắt đầu (s)</Label><Input type="number" step="0.1" min={0} disabled={!canEdit} value={v.start} onChange={(e) => update((t) => ({ ...t, voiceover: t.voiceover.map((x, j) => (j === i ? { ...x, start: num(e.target.value) } : x)) }))} /></div>
                    <div><Label className="text-xs">Âm lượng</Label><Input type="number" step="0.1" min={0} max={2} disabled={!canEdit} value={v.volume} onChange={(e) => update((t) => ({ ...t, voiceover: t.voiceover.map((x, j) => (j === i ? { ...x, volume: num(e.target.value, 1) } : x)) }))} /></div>
                    {canEdit && <Button size="icon" variant="ghost" aria-label="Xoá voice-over" onClick={() => update((t) => ({ ...t, voiceover: t.voiceover.filter((_, j) => j !== i) }))}><Trash2 /></Button>}
                  </div>
                ))}
                {canEdit && tl.voiceover.length < 5 && <Button size="sm" variant="outline" onClick={() => update((t) => ({ ...t, voiceover: [...t.voiceover, { asset_id: audioOpts[0]?.id ?? "", start: 0, volume: 1 }] }))} data-testid="add-voiceover"><Plus />Thêm voice-over</Button>}
              </div>
              <div className="space-y-2 border-t border-slate-100 pt-3" data-testid="music">
                <div className="flex items-center gap-2"><Switch checked={!!tl.music} disabled={!canEdit} onCheckedChange={(on) => update((t) => ({ ...t, music: on ? { asset_id: audioOpts[0]?.id ?? "", volume: 0.15, fade_out: 2 } : null }))} data-testid="music-toggle" /><span className="text-sm font-medium">Nhạc nền</span></div>
                {tl.music && (
                  <div className="grid gap-2 md:grid-cols-3">
                    <NativeSelect disabled={!canEdit} value={tl.music.asset_id} onChange={(e) => update((t) => ({ ...t, music: { ...t.music!, asset_id: e.target.value } }))} data-testid="music-asset">
                      <option value="">— chọn audio —</option>{audioOpts.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
                    </NativeSelect>
                    <div><Label className="text-xs">Âm lượng (0–1)</Label><Input type="number" step="0.05" min={0} max={1} disabled={!canEdit} value={tl.music.volume} onChange={(e) => update((t) => ({ ...t, music: { ...t.music!, volume: num(e.target.value, 0.15) } }))} /></div>
                    <div><Label className="text-xs">Fade out (s)</Label><Input type="number" step="0.5" min={0} max={10} disabled={!canEdit} value={tl.music.fade_out} onChange={(e) => update((t) => ({ ...t, music: { ...t.music!, fade_out: num(e.target.value, 2) } }))} /></div>
                  </div>
                )}
              </div>
              <Can perm="asset.upload"><div className="border-t border-slate-100 pt-3"><p className="mb-1 text-xs text-slate-500">Tải audio mới (voice-over / nhạc nền)</p>
                <AssetUploader defaultType="AUDIO" lockType compact accept="audio/*" projectId={pid} channelId={project.channel_id} onUploaded={() => qc.invalidateQueries({ queryKey: ["assets", "AUDIO"] })} /></div></Can>
            </CardContent>
          </Card>
        </div>

        <div className="space-y-4">
          <Card>
            <CardHeader><CardTitle>Phụ đề · Logo · Thumbnail</CardTitle></CardHeader>
            <CardContent className="space-y-4 text-sm">
              <div className="space-y-2" data-testid="subtitles">
                <div className="flex items-center gap-2"><Switch checked={tl.subtitles.enabled} disabled={!canEdit} onCheckedChange={(v) => update((t) => ({ ...t, subtitles: { ...t.subtitles, enabled: v } }))} data-testid="subs-toggle" />Phụ đề tiếng Việt (từ lời thoại)</div>
                <div className="flex items-center gap-2"><Switch checked={tl.subtitles.burn_in} disabled={!canEdit || !tl.subtitles.enabled} onCheckedChange={(v) => update((t) => ({ ...t, subtitles: { ...t.subtitles, burn_in: v } }))} />Burn-in vào video (vẫn xuất file .srt)</div>
                <div><Label className="text-xs">Cỡ chữ (6–24)</Label><Input type="number" min={6} max={24} disabled={!canEdit} value={tl.subtitles.font_size} onChange={(e) => update((t) => ({ ...t, subtitles: { ...t.subtitles, font_size: num(e.target.value, 10) } }))} /></div>
              </div>
              <div className="space-y-2 border-t border-slate-100 pt-3" data-testid="logo">
                <div className="flex items-center gap-2"><Switch checked={!!tl.logo} disabled={!canEdit} onCheckedChange={(on) => update((t) => ({ ...t, logo: on ? { asset_id: logoOpts[0]?.id ?? "", position: "top_right", scale: 0.18, opacity: 0.9 } : null }))} data-testid="logo-toggle" />Logo thương hiệu</div>
                {tl.logo && (
                  <>
                    <NativeSelect disabled={!canEdit} value={tl.logo.asset_id} onChange={(e) => update((t) => ({ ...t, logo: { ...t.logo!, asset_id: e.target.value } }))}><option value="">— chọn logo —</option>{logoOpts.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}</NativeSelect>
                    <AssetImage assetId={tl.logo.asset_id || null} alt="Logo" className="h-16 w-16 object-contain" />
                    <div className="grid grid-cols-3 gap-2">
                      <NativeSelect disabled={!canEdit} value={tl.logo.position} onChange={(e) => update((t) => ({ ...t, logo: { ...t.logo!, position: e.target.value } }))}>{Object.entries(POS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</NativeSelect>
                      <Input type="number" step="0.01" min={0.05} max={0.5} disabled={!canEdit} value={tl.logo.scale} aria-label="Tỉ lệ logo" onChange={(e) => update((t) => ({ ...t, logo: { ...t.logo!, scale: num(e.target.value, 0.18) } }))} />
                      <Input type="number" step="0.05" min={0.1} max={1} disabled={!canEdit} value={tl.logo.opacity} aria-label="Độ mờ logo" onChange={(e) => update((t) => ({ ...t, logo: { ...t.logo!, opacity: num(e.target.value, 0.9) } }))} />
                    </div>
                  </>
                )}
                {!logoOpts.length && <p className="text-xs text-amber-700">Chưa có logo trong Thư viện (M12) — tải asset loại LOGO.</p>}
              </div>
              <div className="space-y-2 border-t border-slate-100 pt-3" data-testid="thumbnail">
                <p className="font-medium">Thumbnail</p>
                <div className="grid grid-cols-[90px_1fr] gap-2">
                  <div><Label className="text-xs">Thời điểm (s)</Label><Input type="number" step="0.5" min={0} disabled={!canEdit} value={tl.thumbnail.time_sec} onChange={(e) => update((t) => ({ ...t, thumbnail: { ...t.thumbnail, time_sec: num(e.target.value, 1) } }))} /></div>
                  <div><Label className="text-xs">Tiêu đề</Label><Input maxLength={80} disabled={!canEdit} value={tl.thumbnail.title ?? ""} onChange={(e) => update((t) => ({ ...t, thumbnail: { ...t.thumbnail, title: e.target.value || null } }))} data-testid="thumb-title" /></div>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader><CardTitle>Tác vụ render</CardTitle></CardHeader>
            <CardContent className="space-y-2 text-xs" data-testid="render-jobs">
              {(jobs.data ?? []).slice(0, 5).map((j) => (
                <div key={j.id} className="rounded border border-slate-200 p-2">
                  <div className="flex items-center justify-between"><StatusBadge map={JOB_STATUS} value={j.status} /><span>Lần {j.attempt_no}/{j.max_retries + 1} · {formatDate(j.created_at)}</span></div>
                  {j.error_message && <p className="mt-1 text-red-700">{j.error_message}</p>}
                  <p className="mt-1 text-slate-500">{j.log.slice(-1)[0]?.msg}</p>
                </div>
              ))}
              {!jobs.data?.length && <p className="text-slate-500">Chưa render lần nào.</p>}
            </CardContent>
          </Card>
        </div>
      </div>

      <Card>
        <CardHeader><CardTitle>Lịch sử render</CardTitle><CardDescription>Mỗi lần Export tạo một phiên bản MP4 + thumbnail + phụ đề SRT.</CardDescription></CardHeader>
        <CardContent>
          <QueryView q={renders} isEmpty={(d) => !d.length} empty={<EmptyState title="Chưa có bản render" />}>
            {(d) => (
              <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4" data-testid="render-history">
                {d.map((r) => (
                  <div key={r.id} className="space-y-2 rounded-xl border border-slate-200 p-3" data-testid="render-item">
                    <div className="flex items-center justify-between"><b>v{r.version_no}</b><Badge variant={r.status === "APPROVED" ? "green" : r.status === "QC_FAILED" ? "red" : "gray"}>{r.status}</Badge></div>
                    <VideoPlayer assetId={r.video_asset_id} poster={r.thumbnail_asset_id} className="max-h-72" />
                    <p className="text-xs text-slate-500" data-testid="render-meta">{r.width}x{r.height} · {r.duration_sec.toFixed(1)}s · {formatBytes(r.size_bytes)} · {formatDate(r.created_at)}</p>
                    <div className="flex flex-wrap gap-1">
                      <Button size="sm" variant="outline" asChild><a href={assetUrl(r.video_asset_id, true)} data-testid="download-mp4"><Download />MP4</a></Button>
                      {r.subtitle_asset_id && <Button size="sm" variant="outline" asChild><a href={assetUrl(r.subtitle_asset_id, true)}><Download />SRT</a></Button>}
                      {r.thumbnail_asset_id && <Button size="sm" variant="outline" asChild><a href={assetUrl(r.thumbnail_asset_id, true)}><Download />Thumbnail</a></Button>}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </QueryView>
        </CardContent>
      </Card>
    </div>
  );
}

export default function EditorPage() {
  const [pid, setPid] = useProjectParam();
  const project = useQuery<Project>({ queryKey: ["project", pid], queryFn: () => api(`/projects/${pid}`), enabled: !!pid,
    refetchInterval: (q) => (q.state.data?.status === "RENDERING" ? 3000 : false) });
  return (
    <RequirePermission perm="project.view">
      <PageHeader code="M06" title="AI Video Editor" description="Timeline cơ bản, cắt ghép cảnh, voice-over, nhạc nền, phụ đề, logo, thumbnail và Export MP4 bằng FFmpeg."
        actions={<ProjectPicker value={pid} onChange={setPid} statuses={["GENERATING", "NEEDS_MANUAL_ACTION", "SCENE_QC", "RENDERING", "FINAL_QC", "APPROVAL_PENDING", "APPROVED", "PUBLISH_QUEUED", "PUBLISHED", "ANALYTICS_COLLECTION", "FEEDBACK_REVIEW", "RETRY_PENDING", "FAILED"]} />} />
      {!pid ? <EmptyState title="Chọn dự án" description="Chọn dự án đã có cảnh video để dựng." /> : (
        <QueryView q={project}>{(p) => <Editor key={p.id} project={p} />}</QueryView>
      )}
    </RequirePermission>
  );
}
