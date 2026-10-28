"use client";
import Link from "next/link";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, XCircle } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/hooks/use-auth";
import { useAction } from "@/hooks/use-mutate";
import { PageHeader } from "@/components/app/page-header";
import { RequirePermission, Can } from "@/components/app/require";
import { EmptyState, QueryView } from "@/components/app/states";
import { StatusBadge } from "@/components/app/status-badge";
import { ProjectPicker, useProjectParam } from "@/components/app/project-picker";
import { VideoPlayer } from "@/components/app/media";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/input";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { PROJECT_STATUS } from "@/lib/labels";
import { assetUrl } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import { ScoreForm } from "@/features/quality/score-form";
import { FindingsTable } from "@/features/quality/findings";
import type { QCView, QueueItem } from "@/features/quality/types";

const QC_STATES = ["SCENE_QC", "FINAL_QC", "APPROVAL_PENDING", "APPROVED", "PUBLISH_QUEUED", "PUBLISHED", "ANALYTICS_COLLECTION"];

function Queue({ onPick }: { onPick: (id: string) => void }) {
  const q = useQuery<QueueItem[]>({ queryKey: ["qc-queue"], queryFn: () => api("/qc/queue") });
  return (
    <Card>
      <CardHeader><CardTitle>Hàng đợi QC</CardTitle></CardHeader>
      <CardContent>
        <QueryView q={q} isEmpty={(d) => d.length === 0} empty={<EmptyState title="Không có video chờ QC" />}>
          {(d) => (
            <Table data-testid="qc-queue">
              <THead><TR><TH>Mã</TH><TH>Tiêu đề</TH><TH>Trạng thái</TH><TH>Lỗi mở</TH><TH>Cập nhật</TH><TH></TH></TR></THead>
              <TBody>
                {d.map((p) => (
                  <TR key={p.id} data-testid="qc-queue-row">
                    <TD className="font-mono text-xs">{p.code}</TD>
                    <TD className="max-w-xs truncate">{p.title}</TD>
                    <TD><StatusBadge map={PROJECT_STATUS} value={p.status} /></TD>
                    <TD>{p.open_findings > 0 ? <Badge variant="red">{p.open_findings}</Badge> : "0"}</TD>
                    <TD className="text-xs">{formatDate(p.updated_at)}</TD>
                    <TD><Button size="sm" variant="outline" onClick={() => onPick(p.id)} data-testid="qc-open">Mở</Button></TD>
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

function ApprovalBox({ view, onDone }: { view: QCView; onDone: () => void }) {
  const [comment, setComment] = useState("");
  const act = useAction((decision: string) => api(`/projects/${view.project.id}/approve`, { body: { decision, comment } }),
    { success: "Đã ghi nhận quyết định", onSuccess: () => { setComment(""); onDone(); } });
  return (
    <Card className="border-orange-200" data-testid="approval-box">
      <CardHeader><CardTitle>Phê duyệt phát hành</CardTitle></CardHeader>
      <CardContent className="space-y-3">
        <Textarea placeholder="Nhận xét (bắt buộc khi từ chối)" value={comment} onChange={(e) => setComment(e.target.value)} data-testid="approval-comment" />
        <div className="flex gap-2">
          <Button variant="success" onClick={() => act.mutate("APPROVED")} loading={act.isPending} data-testid="approve-btn"><CheckCircle2 />Phê duyệt</Button>
          <Button variant="destructive" onClick={() => act.mutate("REJECTED")} loading={act.isPending} disabled={comment.trim().length < 3} data-testid="reject-btn"><XCircle />Từ chối</Button>
        </div>
      </CardContent>
    </Card>
  );
}

function ProjectQC({ id }: { id: string }) {
  const { has } = useAuth();
  const q = useQuery<QCView>({ queryKey: ["qc", id], queryFn: () => api(`/projects/${id}/qc`) });
  return (
    <QueryView q={q}>
      {(v) => {
        const human = v.reviews.filter((r) => r.review_type === "FINAL" && r.reviewer_type === "HUMAN" && r.render_id === v.render?.id)[0];
        const openBlocking = v.findings.filter((f) => f.status === "OPEN" && v.policy.blocking_severities.includes(f.severity));
        const openCritical = openBlocking.filter((f) => f.severity === "CRITICAL");
        const checks = [
          { ok: !!human && human.total_score >= v.policy.min_total, label: `Tổng điểm QC ≥ ${v.policy.min_total}/100 (hiện: ${human ? human.total_score : "chưa chấm"})` },
          { ok: openCritical.length === 0, label: "Không có Critical Error" },
          { ok: openBlocking.length === 0, label: `Không còn lỗi nghiêm trọng chưa xử lý (${openBlocking.length})` },
          { ok: has("project.approve"), label: "Người có quyền phê duyệt (project.approve)" },
        ];
        const auto = v.agent_final?.automated_checks as Record<string, number | null> | undefined;
        return (
          <div className="space-y-4">
            <div className="flex flex-wrap items-center gap-3">
              <StatusBadge map={PROJECT_STATUS} value={v.project.status} />
              <Link href={`/projects/${v.project.id}`} className="text-sm text-brand-600 hover:underline">{v.project.code} · {v.project.title}</Link>
            </div>
            <div className="grid gap-4 lg:grid-cols-3">
              <Card>
                <CardHeader><CardTitle>Bản render {v.render ? `v${v.render.version_no}` : ""}</CardTitle></CardHeader>
                <CardContent className="space-y-2 text-sm">
                  {v.render ? (<>
                    <VideoPlayer assetId={v.render.video_asset_id} poster={v.render.thumbnail_asset_id} className="max-h-[480px]" />
                    <p>{v.render.width}×{v.render.height} · {v.render.duration_sec.toFixed(1)}s</p>
                    {v.render.subtitle_asset_id && <a className="text-brand-600 hover:underline" href={assetUrl(v.render.subtitle_asset_id, true)}>Tải phụ đề SRT</a>}
                  </>) : <p className="text-slate-500">Chưa có bản render — dự án ở bước {PROJECT_STATUS[v.project.status]?.label}.</p>}
                </CardContent>
              </Card>
              <Card className="lg:col-span-2">
                <CardHeader><CardTitle>Gợi ý của A07 AI QC</CardTitle></CardHeader>
                <CardContent className="space-y-2 text-sm" data-testid="agent-suggest">
                  {v.agent_final ? (<>
                    <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
                      <div><p className="text-slate-500">Độ ồn</p><p>{auto?.integrated_lufs ?? "—"} LUFS</p></div>
                      <div><p className="text-slate-500">Đỉnh</p><p>{auto?.true_peak_dbfs ?? "—"} dBFS</p></div>
                      <div><p className="text-slate-500">Khung đen</p><p>{auto?.black_seconds ?? 0}s</p></div>
                      <div><p className="text-slate-500">Lặng dài nhất</p><p>{auto?.longest_silence ?? 0}s</p></div>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {v.criteria.map((c) => {
                        const s = v.agent_final!.scores[c.key];
                        return <Badge key={c.key} variant={s?.score === null || s?.score === undefined ? "gray" : "default"}>{c.label}: {s?.score ?? "chờ người chấm"}</Badge>;
                      })}
                    </div>
                    <p className="text-xs text-slate-500">Cần người đánh giá: {v.agent_final.pending_manual.map((k) => v.criteria.find((c) => c.key === k)?.label ?? k).join(", ")}</p>
                    <p className="text-xs text-slate-500">{v.agent_final.notes}</p>
                  </>) : <p className="text-slate-500">Chưa có kết quả QC tự động cho bản render này.</p>}
                </CardContent>
              </Card>
            </div>
            <Card data-testid="release-conditions">
              <CardHeader><CardTitle>Điều kiện phát hành</CardTitle></CardHeader>
              <CardContent className="grid gap-1 text-sm md:grid-cols-2">
                {checks.map((c) => <p key={c.label} className={c.ok ? "text-emerald-700" : "text-red-700"}>{c.ok ? "✓" : "✗"} {c.label}</p>)}
              </CardContent>
            </Card>
            {v.project.status === "FINAL_QC" && v.render && <Can perm="qc.review"><ScoreForm view={v} onDone={() => q.refetch()} /></Can>}
            {v.project.status === "APPROVAL_PENDING" && <Can perm="project.approve"><ApprovalBox view={v} onDone={() => q.refetch()} /></Can>}
            <FindingsTable findings={v.findings} criteria={v.criteria} onChange={() => q.refetch()} />
            <Card>
              <CardHeader><CardTitle>Lịch sử đánh giá & phê duyệt</CardTitle></CardHeader>
              <CardContent>
                <Table data-testid="review-history">
                  <THead><TR><TH>Thời gian</TH><TH>Loại</TH><TH>Người chấm</TH><TH>Tổng</TH><TH>Kết quả</TH><TH>Ghi chú</TH></TR></THead>
                  <TBody>
                    {v.reviews.map((r) => (
                      <TR key={r.id}>
                        <TD className="text-xs">{formatDate(r.created_at)}</TD>
                        <TD>{r.review_type === "FINAL" ? "Tổng thể" : "Cảnh"}</TD>
                        <TD>{r.reviewer_type === "AGENT" ? "A07 AI QC" : "Quality Reviewer"}</TD>
                        <TD>{r.review_type === "FINAL" ? r.total_score : "—"}</TD>
                        <TD><Badge variant={r.result === "PASS" ? "green" : r.result === "FAIL" ? "red" : "yellow"}>{r.result}</Badge></TD>
                        <TD className="max-w-sm truncate text-xs" title={r.notes}>{r.notes}</TD>
                      </TR>
                    ))}
                    {v.approvals.map((a) => (
                      <TR key={a.id}>
                        <TD className="text-xs">{formatDate(a.created_at)}</TD><TD>Phê duyệt</TD><TD>—</TD><TD>—</TD>
                        <TD><Badge variant={a.decision === "APPROVED" ? "green" : "red"}>{a.decision === "APPROVED" ? "Đã duyệt" : "Từ chối"}</Badge></TD>
                        <TD className="text-xs">{a.comment}</TD>
                      </TR>
                    ))}
                  </TBody>
                </Table>
              </CardContent>
            </Card>
          </div>
        );
      }}
    </QueryView>
  );
}

export default function QualityPage() {
  const [project, setProject] = useProjectParam();
  return (
    <RequirePermission perm="qc.view">
      <PageHeader code="M07" title="Quality Control" description="Chấm 10 tiêu chí, xử lý lỗi, phê duyệt phát hành. Điều kiện: ≥ 98/100, không Critical, không lỗi nghiêm trọng mở, người có quyền phê duyệt."
        actions={<ProjectPicker statuses={QC_STATES} value={project} onChange={setProject} />} />
      {project ? <ProjectQC id={project} /> : <Queue onPick={setProject} />}
    </RequirePermission>
  );
}
