"use client";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { FastForward, RotateCcw, Wrench, XCircle } from "lucide-react";
import { api } from "@/lib/api";
import { useAction } from "@/hooks/use-mutate";
import { PageHeader } from "@/components/app/page-header";
import { RequirePermission, Can } from "@/components/app/require";
import { QueryView } from "@/components/app/states";
import { StatusBadge } from "@/components/app/status-badge";
import { ConfirmButton } from "@/components/app/confirm";
import { VideoPlayer } from "@/components/app/media";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/misc";
import { PROJECT_STATUS, SCENE_STATUS, JOB_STATUS, AUTOMATION } from "@/lib/labels";
import { formatDate, formatVND } from "@/lib/utils";
import type { Project } from "@/types/api";

type Overview = {
  project: Project; step: { label: string; owner: string; input: string; output: string; permission: string | null } | null;
  allowed_transitions: string[]; waiting_for: string | null;
  scenes: { id: string; order_index: number; title: string; status: string; selected_asset_id: string | null }[];
  jobs_by_status: Record<string, number>;
  renders: { id: string; version_no: number; video_asset_id: string; thumbnail_asset_id: string | null; status: string; duration_sec: number }[];
  render_jobs: { id: string; status: string; attempt_no: number; error: string | null; log: { msg: string; at?: string }[] }[];
  cost_total: number;
  events: { id: string; created_at: string; from_status: string | null; to_status: string; actor_type: string; actor_ref: string | null; note: string }[];
};

const SCREEN_FOR: Record<string, [string, string]> = {
  CREATED: ["/scripts", "Mở M03 — Kịch bản"], SCRIPT_GENERATING: ["/scripts", "Mở M03 — Kịch bản"], SCRIPT_REVIEW: ["/scripts", "Duyệt kịch bản (M03)"],
  STORYBOARD_READY: ["/production", "Mở M05 — Sản xuất"], ASSET_VALIDATION: ["/production", "Mở M05"], GENERATION_QUEUED: ["/production", "Mở M05"],
  GENERATING: ["/production", "Mở M05"], NEEDS_MANUAL_ACTION: ["/production", "Xử lý tại M05"], SCENE_QC: ["/production", "QC cảnh (M05)"],
  RENDERING: ["/editor", "Mở M06 — Editor"], FINAL_QC: ["/quality", "Chấm QC (M07)"], APPROVAL_PENDING: ["/quality", "Phê duyệt (M07)"],
  APPROVED: ["/publishing", "Lên lịch đăng (M10)"], PUBLISH_QUEUED: ["/publishing", "Xuất bản (M10)"], PUBLISHED: ["/publishing", "Nhập analytics (M10)"],
  ANALYTICS_COLLECTION: ["/publishing", "Analytics (M10)"],
};

export default function ProjectDetail() {
  const { id } = useParams<{ id: string }>();
  const q = useQuery<Overview>({ queryKey: ["project-overview", id], queryFn: () => api(`/projects/${id}/overview`),
    refetchInterval: (query) => (["GENERATING", "RENDERING", "GENERATION_QUEUED"].includes(query.state.data?.project.status ?? "") ? 3000 : false) });
  const inv = [["project-overview", id], ["projects"]];
  const advance = useAction(() => api<{ steps: string[]; waiting_for: string | null }>(`/projects/${id}/advance`, { method: "POST" }),
    { success: (r) => (r.steps.length ? `AI Director: ${r.steps.join(" → ")}` : `Đang chờ: ${r.waiting_for ?? "—"}`), invalidate: inv });
  const retry = useAction(() => api(`/projects/${id}/retry`, { body: { note: "Retry từ M11" } }), { success: "Đã chạy lại bước lỗi", invalidate: inv });
  const resolve = useAction(() => api(`/projects/${id}/resolve-manual`, { body: { note: "Đã xử lý thủ công" } }), { success: "Đã kiểm tra lại", invalidate: inv });

  return (
    <RequirePermission perm="project.view">
      <QueryView q={q}>
        {(d) => {
          const p = d.project;
          const link = SCREEN_FOR[p.status];
          return (
            <>
              <PageHeader code={`M11 · ${p.code}`} title={p.title} description={`${p.channel.name} · ${AUTOMATION[p.automation_level] ?? p.automation_level} · Provider: ${p.video_provider_code}`}
                actions={<>
                  {link && <Button variant="outline" asChild><Link href={`${link[0]}?project=${p.id}`}>{link[1]}</Link></Button>}
                  <Can perm="project.edit"><Button onClick={() => advance.mutate(undefined)} loading={advance.isPending} data-testid="advance"><FastForward />AI Director chạy tiếp</Button></Can>
                  {["FAILED", "RETRY_PENDING"].includes(p.status) && <Can perm="project.edit"><Button variant="secondary" onClick={() => retry.mutate(undefined)} loading={retry.isPending} data-testid="retry-project"><RotateCcw />Retry</Button></Can>}
                  {p.status === "NEEDS_MANUAL_ACTION" && <Can perm="project.edit"><Button variant="secondary" onClick={() => resolve.mutate(undefined)} loading={resolve.isPending} data-testid="resolve-manual"><Wrench />Đã xử lý — kiểm tra lại</Button></Can>}
                  {d.allowed_transitions.includes("CANCELLED") && (
                    <Can perm="project.cancel">
                      <ConfirmButton variant="destructive" title="Huỷ dự án?" description="Các tác vụ đang chờ sẽ bị huỷ." requireReason data-testid="cancel-project"
                        onConfirm={async (reason) => { await api(`/projects/${id}/cancel`, { body: { note: reason } }); q.refetch(); }}>
                        <XCircle />Huỷ
                      </ConfirmButton>
                    </Can>
                  )}
                </>} />
              <div className="grid gap-4 lg:grid-cols-3">
                <Card className="lg:col-span-2">
                  <CardHeader><CardTitle>Tiến độ workflow</CardTitle></CardHeader>
                  <CardContent className="space-y-3">
                    <div className="flex flex-wrap items-center gap-3">
                      <StatusBadge map={PROJECT_STATUS} value={p.status} />
                      {p.data_mode === "DEMO" && <Badge variant="yellow">DEMO</Badge>}
                      <span className="text-sm text-slate-500">Bước: <b>{d.step?.label}</b> · Phụ trách: {d.step?.owner}</span>
                    </div>
                    <Progress value={p.progress} />
                    {d.waiting_for && <p className="rounded-lg bg-brand-50 p-2 text-sm text-brand-700" data-testid="waiting-for">⏳ {d.waiting_for}</p>}
                    {p.last_error && <p className="rounded-lg bg-red-50 p-2 text-sm text-red-700" data-testid="last-error">{p.last_error}</p>}
                    <div className="grid grid-cols-2 gap-2 text-sm md:grid-cols-4">
                      <div><p className="text-slate-500">Đầu vào</p><p>{d.step?.input}</p></div>
                      <div><p className="text-slate-500">Đầu ra</p><p>{d.step?.output}</p></div>
                      <div><p className="text-slate-500">Chi phí</p><p data-testid="project-cost">{formatVND(d.cost_total)}</p></div>
                      <div><p className="text-slate-500">Retry</p><p>{p.retry_count}</p></div>
                    </div>
                    <div>
                      <p className="mb-1 text-sm font-medium">Cảnh</p>
                      <div className="flex flex-wrap gap-2">
                        {d.scenes.map((s) => <span key={s.id} className="flex items-center gap-1 text-xs">#{s.order_index + 1}<StatusBadge map={SCENE_STATUS} value={s.status} /></span>)}
                        {!d.scenes.length && <span className="text-sm text-slate-500">Chưa có storyboard</span>}
                      </div>
                    </div>
                    {Object.keys(d.jobs_by_status).length > 0 && (
                      <div className="flex flex-wrap gap-2 text-xs">
                        {Object.entries(d.jobs_by_status).map(([s, n]) => <span key={s} className="flex items-center gap-1"><StatusBadge map={JOB_STATUS} value={s} />×{n}</span>)}
                      </div>
                    )}
                  </CardContent>
                </Card>
                <Card>
                  <CardHeader><CardTitle>Bản render mới nhất</CardTitle></CardHeader>
                  <CardContent>
                    {d.renders[0] ? <VideoPlayer assetId={d.renders[0].video_asset_id} poster={d.renders[0].thumbnail_asset_id} className="max-h-96" /> : <p className="text-sm text-slate-500">Chưa render</p>}
                    {d.render_jobs[0] && (
                      <div className="mt-2 text-xs text-slate-500">
                        Render job: <StatusBadge map={JOB_STATUS} value={d.render_jobs[0].status} /> lần {d.render_jobs[0].attempt_no}
                        {d.render_jobs[0].error && <p className="text-red-700">{d.render_jobs[0].error}</p>}
                      </div>
                    )}
                  </CardContent>
                </Card>
              </div>
              <Card className="mt-4">
                <CardHeader><CardTitle>Nhật ký thực thi</CardTitle></CardHeader>
                <CardContent>
                  <ol className="relative space-y-3 border-l border-slate-200 pl-4" data-testid="event-log">
                    {[...d.events].reverse().map((e) => (
                      <li key={e.id} className="text-sm">
                        <span className="absolute -left-1.5 mt-1.5 h-3 w-3 rounded-full bg-brand-500" />
                        <div className="flex flex-wrap items-center gap-2">
                          {e.from_status && <><StatusBadge map={PROJECT_STATUS} value={e.from_status} />→</>}
                          <StatusBadge map={PROJECT_STATUS} value={e.to_status} />
                          <span className="text-xs text-slate-500">{formatDate(e.created_at)} · {e.actor_type === "AGENT" ? `Agent ${e.actor_ref}` : e.actor_type === "USER" ? "Người dùng" : "Hệ thống"}</span>
                        </div>
                        {e.note && <p className="mt-0.5 text-slate-600">{e.note}</p>}
                      </li>
                    ))}
                  </ol>
                </CardContent>
              </Card>
            </>
          );
        }}
      </QueryView>
    </RequirePermission>
  );
}
