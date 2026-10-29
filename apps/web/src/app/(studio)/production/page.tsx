"use client";
import Link from "next/link";
import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Clapperboard, Film, PlayCircle, RotateCcw, SearchCheck, Wrench } from "lucide-react";
import { toast } from "sonner";
import { api, ApiError, errorMessage } from "@/lib/api";
import { useAction } from "@/hooks/use-mutate";
import { PageHeader } from "@/components/app/page-header";
import { RequirePermission, Can } from "@/components/app/require";
import { EmptyState, QueryView } from "@/components/app/states";
import { StatusBadge } from "@/components/app/status-badge";
import { ProjectPicker, useProjectParam } from "@/components/app/project-picker";
import { VideoPlayer } from "@/components/app/media";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { JOB_STATUS, PROJECT_STATUS, SCENE_STATUS } from "@/lib/labels";
import { formatDate, formatVND } from "@/lib/utils";
import type { Asset, GenerationJob, Project, Scene } from "@/types/api";
import { FlowImportDialog, SceneQCDialog } from "@/features/production/scene-dialogs";

type Row = { scene: Scene; jobs: GenerationJob[]; outputs: Asset[]; attempts_this_version: number; cost_total: number };
type Provider = { code: string; name: string; kind: string; is_real: boolean; available: boolean; connection_status: string; unit_cost_vnd_per_sec: number; max_duration_sec: number };
type Report = { blocking: string[]; warnings: string[]; estimated_cost: number; provider: { name: string; kind: string }; budget_allowed: boolean };

const KIND: Record<string, { label: string; variant: "yellow" | "purple" | "green" }> = {
  MOCK: { label: "Mock Provider (DEMO — không phải AI thật)", variant: "yellow" },
  MANUAL: { label: "Manual Flow Import", variant: "purple" },
  REAL_API: { label: "Real API Provider", variant: "green" },
};
const ACTIVE = ["GENERATING", "RENDERING", "GENERATION_QUEUED"];

function Providers({ project, refresh }: { project?: Project; refresh: () => void }) {
  const current = project?.video_provider_code ?? "";
  const q = useQuery<Provider[]>({ queryKey: ["video-providers"], queryFn: () => api("/video-providers") });
  const use = useAction((code: string) => api(`/projects/${project?.id}`, { method: "PATCH", body: { video_provider_code: code } }),
    { success: "Đã đổi nhà cung cấp — bấm 'Tạo các cảnh còn thiếu' để tạo tự động", onSuccess: refresh });
  return (
    <Card>
      <CardHeader><CardTitle className="text-sm">Nhà cung cấp video</CardTitle><CardDescription>Google Flow không có API công khai — chỉ nhập thủ công. Real API chỉ dùng khi đã kết nối & xác minh ở M15.</CardDescription></CardHeader>
      <CardContent className="space-y-2" data-testid="providers">
        {(q.data ?? []).map((p) => (
          <div key={p.code} className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-slate-200 p-2 text-sm" data-testid={`provider-${p.code}`}>
            <span className="font-medium">{p.name} {p.code === current && <Badge variant="navy">Dự án dùng</Badge>}</span>
            <span className="flex items-center gap-1">
              <Badge variant={KIND[p.kind]?.variant ?? "gray"}>{KIND[p.kind]?.label ?? p.kind}</Badge>
              <Badge variant={p.available ? "green" : "gray"}>{p.available ? "Khả dụng" : "Không khả dụng"}</Badge>
              <Badge variant="gray">{p.connection_status}</Badge>
              <span className="text-xs text-slate-500">{formatVND(p.unit_cost_vnd_per_sec)}/giây</span>
              {project && p.available && p.code !== current && (
                <Can perm="project.edit">
                  <Button size="sm" variant="outline" disabled={use.isPending} data-testid={`use-provider-${p.code}`}
                    onClick={() => { if (!p.is_real || confirm(`Chuyển dự án sang ${p.name}? Mỗi cảnh sẽ tính phí thật khoảng ${formatVND(p.unit_cost_vnd_per_sec)}/giây. Các cảnh đang chờ nhập thủ công sẽ được huỷ.`)) use.mutate(p.code); }}>
                    Dùng cho dự án
                  </Button>
                </Can>
              )}
            </span>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

function SceneRow({ r, project, refresh }: { r: Row; project: Project; refresh: () => void }) {
  const s = r.scene;
  const last = r.jobs[0];
  const n = s.order_index + 1;
  const maxAttempts = (last?.max_retries ?? 3) + 1;
  const regen = useAction(() => api(`/scenes/${s.id}/regenerate`, { method: "POST" }), { success: `Đã xếp hàng tạo lại cảnh ${n}`, onSuccess: refresh });
  const select = useAction((assetId: string) => api(`/scenes/${s.id}/select-output`, { body: { asset_id: assetId } }), { success: "Đã chọn phiên bản", onSuccess: refresh });
  const canProduce = ["GENERATING", "NEEDS_MANUAL_ACTION", "SCENE_QC", "FINAL_QC", "GENERATION_QUEUED"].includes(project.status);
  return (
    <Card data-testid={`prod-scene-${s.order_index}`}>
      <CardContent className="grid gap-4 pt-5 md:grid-cols-[180px_1fr]">
        <div className="space-y-2">
          <VideoPlayer assetId={s.selected_asset_id} className="max-h-80" />
          {r.outputs.length > 1 && (
            <div className="space-y-1 text-xs">
              <p className="font-medium text-slate-600">Phiên bản đã tạo</p>
              {r.outputs.map((a, i) => (
                <button key={a.id} onClick={() => select.mutate(a.id)} disabled={a.id === s.selected_asset_id} data-testid="select-output"
                  className="block w-full rounded border border-slate-200 px-2 py-1 text-left hover:bg-slate-50 disabled:bg-brand-50">
                  #{r.outputs.length - i} · {a.source} · {a.duration_sec?.toFixed(1)}s {a.id === s.selected_asset_id && "✓"}
                </button>
              ))}
            </div>
          )}
        </div>
        <div className="space-y-2">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="font-semibold">Cảnh {n}: {s.title}</p>
            <div className="flex items-center gap-2">
              <StatusBadge map={SCENE_STATUS} value={s.status} />
              {last && <StatusBadge map={JOB_STATUS} value={last.status} />}
              <Badge variant={r.attempts_this_version >= maxAttempts ? "red" : "gray"} data-testid="attempts">Lần {r.attempts_this_version}/{maxAttempts}</Badge>
            </div>
          </div>
          <details className="rounded bg-slate-50 p-2 text-xs"><summary className="cursor-pointer font-medium">Prompt (v{s.current_version_no})</summary><pre className="mt-1 whitespace-pre-wrap font-mono">{s.prompt_text || "Chưa có prompt"}</pre></details>
          {last?.error_message && <p className="rounded bg-red-50 p-2 text-xs text-red-700" data-testid="job-error">{last.error_code}: {last.error_message}</p>}
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead className="text-left text-slate-500"><tr><th className="py-1">Lần</th><th>Provider</th><th>Trạng thái</th><th>Chi phí</th><th>Bắt đầu</th><th>Kết thúc</th></tr></thead>
              <tbody>
                {r.jobs.map((j) => (
                  <tr key={j.id} className="border-t border-slate-100" data-testid="scene-job">
                    <td className="py-1">{j.attempt_no}</td><td>{j.provider_code}</td><td><StatusBadge map={JOB_STATUS} value={j.status} /></td>
                    <td>{formatVND(Number(j.actual_cost) || Number(j.estimated_cost))}{Number(j.actual_cost) === 0 && Number(j.estimated_cost) > 0 && j.status !== "SUCCEEDED" ? " (ước tính)" : ""}</td>
                    <td>{formatDate(j.started_at)}</td><td>{formatDate(j.finished_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="mt-1 text-xs text-slate-500">Tổng chi phí cảnh: <b>{formatVND(r.cost_total)}</b></p>
          </div>
          {canProduce && (
            <div className="flex flex-wrap gap-2">
              <Can perm="generation.run"><Button size="sm" variant="outline" onClick={() => regen.mutate(undefined)} loading={regen.isPending} data-testid={`regen-${s.order_index}`}><RotateCcw />Tạo lại cảnh</Button></Can>
              <Can perm="generation.import"><FlowImportDialog sceneId={s.id} sceneNo={n} onDone={refresh} /></Can>
              {["SCENE_QC", "FINAL_QC", "NEEDS_MANUAL_ACTION"].includes(project.status) && s.selected_asset_id && <Can perm="qc.review"><SceneQCDialog sceneId={s.id} sceneNo={n} onDone={refresh} /></Can>}
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

export default function ProductionPage() {
  const [pid, setPid] = useProjectParam();
  const qc = useQueryClient();
  const [report, setReport] = useState<Report | null>(null);
  const [budgetErr, setBudgetErr] = useState<string | null>(null);
  const project = useQuery<Project>({ queryKey: ["project", pid], queryFn: () => api(`/projects/${pid}`), enabled: !!pid,
    refetchInterval: (q) => (ACTIVE.includes(q.state.data?.status ?? "") ? 3000 : false) });
  const rows = useQuery<Row[]>({ queryKey: ["production", pid], queryFn: () => api(`/projects/${pid}/production`), enabled: !!pid,
    refetchInterval: () => (ACTIVE.includes(project.data?.status ?? "") ? 3000 : false) });
  const refresh = () => { qc.invalidateQueries({ queryKey: ["production", pid] }); qc.invalidateQueries({ queryKey: ["project", pid] }); };
  const validate = useAction(() => api<Report>(`/projects/${pid}/validate-assets`, { method: "POST" }),
    { success: (r) => (r.blocking.length ? "Thiếu điều kiện — cần xử lý thủ công" : "Tài nguyên hợp lệ"), onSuccess: (r) => { setReport(r); refresh(); } });
  const generate = async () => {
    setBudgetErr(null);
    try {
      const jobs = await api<GenerationJob[]>(`/projects/${pid}/generate`, { body: {} });
      toast.success(`Đã gửi ${jobs.length} tác vụ tạo cảnh`);
    } catch (e) {
      if (e instanceof ApiError && e.code === "BUDGET_EXCEEDED") setBudgetErr(e.message);
      toast.error(errorMessage(e));
    } finally { refresh(); }
  };
  const render = useAction(() => api(`/projects/${pid}/render`, { method: "POST" }), { success: "Đã bắt đầu render", onSuccess: refresh });
  const resolve = useAction(() => api(`/projects/${pid}/resolve-manual`, { body: { note: "Đã xử lý tại M05" } }), { success: "Đã kiểm tra lại", onSuccess: refresh });
  const p = project.data;
  return (
    <RequirePermission perm="project.view">
      <PageHeader code="M05" title="Video Production" description="Tạo cảnh qua Provider, nhập thủ công từ Google Flow, quản lý phiên bản, retry có giới hạn và kiểm soát ngân sách."
        actions={<ProjectPicker value={pid} onChange={(v) => { setReport(null); setBudgetErr(null); setPid(v); }} />} />
      {!pid ? <EmptyState title="Chọn dự án" description="Chọn dự án đã duyệt kịch bản để sản xuất cảnh." /> : (
        <QueryView q={project}>
          {(pr) => (
            <div className="space-y-4">
              <Card>
                <CardContent className="flex flex-wrap items-center gap-3 pt-5">
                  <Film className="h-5 w-5 text-slate-400" />
                  <b>{pr.code}</b><span className="text-sm">{pr.title}</span>
                  <StatusBadge map={PROJECT_STATUS} value={pr.status} />
                  {pr.data_mode === "DEMO" && <Badge variant="yellow">DEMO</Badge>}
                  <span className="text-xs text-slate-500">Ngân sách dự án: {Number(pr.budget_limit) > 0 ? formatVND(pr.budget_limit) : "không giới hạn riêng"}</span>
                  <div className="ml-auto flex flex-wrap gap-2">
                    {["STORYBOARD_READY", "ASSET_VALIDATION", "NEEDS_MANUAL_ACTION"].includes(pr.status) && (
                      <Can perm="generation.run"><Button variant="outline" onClick={() => validate.mutate(undefined)} loading={validate.isPending} data-testid="validate-assets"><SearchCheck />Kiểm tra tài nguyên</Button></Can>
                    )}
                    {["GENERATION_QUEUED", "GENERATING", "NEEDS_MANUAL_ACTION", "SCENE_QC", "FINAL_QC"].includes(pr.status) && (
                      <Can perm="generation.run"><Button onClick={generate} data-testid="generate"><Clapperboard />Tạo các cảnh còn thiếu</Button></Can>
                    )}
                    {pr.status === "NEEDS_MANUAL_ACTION" && <Can perm="project.edit"><Button variant="secondary" onClick={() => resolve.mutate(undefined)} loading={resolve.isPending} data-testid="resolve-manual"><Wrench />Đã xử lý — tiếp tục</Button></Can>}
                    {pr.status === "SCENE_QC" && <Can perm="render.run"><Button variant="success" onClick={() => render.mutate(undefined)} loading={render.isPending} data-testid="render"><PlayCircle />Render video</Button></Can>}
                    {["FINAL_QC", "RENDERING"].includes(pr.status) && <Button variant="outline" asChild><Link href={`/editor?project=${pr.id}`}>Mở M06 Editor</Link></Button>}
                  </div>
                </CardContent>
              </Card>
              {pr.last_error && pr.status === "NEEDS_MANUAL_ACTION" && <p className="rounded-lg bg-red-50 p-3 text-sm text-red-700" data-testid="project-error">{pr.last_error}</p>}
              {budgetErr && <p className="rounded-lg border border-red-300 bg-red-50 p-3 text-sm font-medium text-red-800" role="alert" data-testid="budget-error">⛔ Vượt ngân sách: {budgetErr}</p>}
              {report && (
                <Card data-testid="asset-report">
                  <CardHeader><CardTitle className="text-sm">Báo cáo kiểm tra tài nguyên (A04)</CardTitle></CardHeader>
                  <CardContent className="space-y-1 text-sm">
                    <p>Provider: {report.provider.name} · Chi phí ước tính: <b>{formatVND(report.estimated_cost)}</b> · Ngân sách: {report.budget_allowed ? "trong hạn mức" : <span className="text-red-700">VƯỢT</span>}</p>
                    {report.blocking.map((b) => <p key={b} className="text-red-700">✗ {b}</p>)}
                    {report.warnings.map((w) => <p key={w} className="text-amber-700">⚠ {w}</p>)}
                    {!report.blocking.length && <p className="text-emerald-700">✓ Đủ điều kiện tạo cảnh</p>}
                  </CardContent>
                </Card>
              )}
              <div className="grid gap-4 xl:grid-cols-[1fr_380px]">
                <QueryView q={rows} isEmpty={(d) => !d.length} empty={<EmptyState title="Chưa có cảnh" description="Duyệt kịch bản tại M03 trước." />}>
                  {(d) => <div className="space-y-3">{d.map((r) => <SceneRow key={r.scene.id} r={r} project={pr} refresh={refresh} />)}</div>}
                </QueryView>
                <Providers project={p} refresh={refresh} />
              </div>
            </div>
          )}
        </QueryView>
      )}
    </RequirePermission>
  );
}
