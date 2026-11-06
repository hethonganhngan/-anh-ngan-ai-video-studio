"use client";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "@/lib/api";
import { useUsers } from "@/hooks/use-lookups";
import { PageHeader } from "@/components/app/page-header";
import { RequirePermission, Can } from "@/components/app/require";
import { QueryView } from "@/components/app/states";
import { StatusBadge } from "@/components/app/status-badge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { FEEDBACK_STATUS, PRIORITY } from "@/lib/labels";
import { cn, formatDate } from "@/lib/utils";
import { CATEGORY_LABEL, EVIDENCE_LABEL, SOURCE_LABEL, STATUS_STEP_INDEX, STEPS, type FeedbackDetail } from "@/features/feedback/types";
import { CancelCapa, CapaForm, CompleteCapa, RcaForm, RestartForm, SimpleAction, StandardizeForm, TriageForm, ValidateForm, VerifyForm } from "@/features/feedback/actions";

function Stepper({ status }: { status: string }) {
  const idx = STATUS_STEP_INDEX[status] ?? 0;
  return (
    <ol className="grid grid-cols-2 gap-2 md:grid-cols-8" data-testid="fb-stepper">
      {STEPS.map((s, i) => {
        const done = i < idx || status === "CLOSED";
        const current = i === idx && status !== "CLOSED";
        return (
          <li key={s.key} data-step={s.key} data-state={done ? "done" : current ? "current" : "todo"}
            className={cn("rounded-lg border p-2 text-center text-xs", done ? "border-emerald-200 bg-emerald-50 text-emerald-800" : current ? (status === "REOPENED" ? "border-red-300 bg-red-50 text-red-800" : "border-brand-500 bg-brand-50 text-brand-700") : "border-slate-200 bg-white text-slate-400")}>
            <p className="font-semibold">{i + 1}. {s.key}</p><p>{s.label}</p>
          </li>
        );
      })}
    </ol>
  );
}

export default function FeedbackDetailPage() {
  const { id } = useParams<{ id: string }>();
  const qc = useQueryClient();
  const users = useUsers();
  const [openCapa, setOpenCapa] = useState<string | null>(null);
  const q = useQuery<FeedbackDetail>({ queryKey: ["feedback-detail", id], queryFn: () => api(`/feedback/${id}`) });
  const onDone = (d: FeedbackDetail) => { qc.setQueryData(["feedback-detail", id], d); qc.invalidateQueries({ queryKey: ["feedback"] }); setOpenCapa(null); };
  const name = (uid: string | null) => users.data?.find((u) => u.id === uid)?.full_name ?? "—";
  return (
    <RequirePermission perm="feedback.view">
      <QueryView q={q}>
        {(d) => {
          const c = d.case;
          const st = c.status;
          return (
            <div className="space-y-4">
              <PageHeader code={`M08 · ${c.code}`} title={c.title} description={`${SOURCE_LABEL[c.source] ?? c.source} · ${CATEGORY_LABEL[c.category] ?? c.category}`}
                actions={<Button variant="outline" asChild><Link href="/feedback">← Danh sách</Link></Button>} />
              <div className="flex flex-wrap items-center gap-2">
                <StatusBadge map={FEEDBACK_STATUS} value={st} />
                {c.priority && <Badge variant={PRIORITY[c.priority]} data-testid="fb-priority-badge">{c.priority}</Badge>}
                <Badge variant="gray">{EVIDENCE_LABEL[c.evidence_class] ?? c.evidence_class}</Badge>
                {d.overdue && <Badge variant="red" data-testid="fb-overdue">Quá hạn</Badge>}
                {c.reopen_count > 0 && <Badge variant="orange">Mở lại {c.reopen_count} lần</Badge>}
              </div>
              <Stepper status={st} />
              <div className="grid gap-4 lg:grid-cols-3">
                <Card className="lg:col-span-2">
                  <CardHeader><CardTitle>Thông tin hồ sơ</CardTitle></CardHeader>
                  <CardContent className="space-y-2 text-sm">
                    <p className="whitespace-pre-line">{c.description || "—"}</p>
                    <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
                      <div><p className="text-slate-500">Người phụ trách</p><p>{name(c.owner_id)}</p></div>
                      <div><p className="text-slate-500">Deadline</p><p>{formatDate(c.deadline)}</p></div>
                      <div><p className="text-slate-500">Người phê duyệt</p><p>{name(c.approver_id)}</p></div>
                      <div><p className="text-slate-500">Video / Cảnh</p><p>{c.project_id ? <Link className="text-brand-600 hover:underline" href={`/projects/${c.project_id}`}>Xem dự án</Link> : "—"}{c.scene_id && ` · cảnh ${c.scene_id.slice(0, 8)}`}</p></div>
                    </div>
                    <div className="grid grid-cols-3 gap-2 rounded-lg bg-slate-50 p-2" data-testid="fb-kpi">
                      <div><p className="text-xs text-slate-500">KPI</p><p>{c.kpi_name ?? "—"}</p></div>
                      <div><p className="text-xs text-slate-500">Trước → Mục tiêu</p><p>{c.kpi_before ?? "—"} → {c.kpi_target ?? "—"}</p></div>
                      <div><p className="text-xs text-slate-500">Sau</p><p>{c.kpi_after ?? "—"}</p></div>
                    </div>
                    {c.standardization_note && <p className="rounded-lg bg-emerald-50 p-2">Chuẩn hoá: {c.standardization_note}</p>}
                  </CardContent>
                </Card>
                <Card>
                  <CardHeader><CardTitle>Bằng chứng ({c.evidence.length})</CardTitle></CardHeader>
                  <CardContent className="space-y-2 text-sm" data-testid="fb-evidence-list">
                    {c.evidence.length === 0 && <p className="text-slate-500">Chưa có bằng chứng</p>}
                    {c.evidence.map((e, i) => <div key={i} className="rounded border border-slate-100 p-2"><Badge variant="gray">{e.type}</Badge> <span className="break-all">{e.ref}</span><p className="text-slate-600">{e.note}</p></div>)}
                  </CardContent>
                </Card>
              </div>

              {st === "NEW" && <Can perm="feedback.manage"><ValidateForm id={id} onDone={onDone} /></Can>}
              {st === "VALIDATED" && <Can perm="feedback.manage"><TriageForm id={id} onDone={onDone} /></Can>}
              {st === "REOPENED" && <Can perm="feedback.manage"><RestartForm id={id} onDone={onDone} /></Can>}
              {st === "RCA_PENDING" && <Can perm="feedback.manage"><RcaForm id={id} onDone={onDone} /></Can>}

              {d.rca.length > 0 && (
                <Card data-testid="fb-rca-list">
                  <CardHeader><CardTitle>Phân tích nguyên nhân gốc</CardTitle></CardHeader>
                  <CardContent className="space-y-3 text-sm">
                    {d.rca.map((r) => (
                      <div key={r.id} className={cn("rounded-lg border p-3", r.is_current ? "border-brand-200" : "border-slate-100 opacity-60")}>
                        <div className="mb-1 flex flex-wrap gap-2"><Badge variant={r.evidence_class === "FACT" ? "green" : "yellow"}>{r.evidence_class}</Badge><Badge variant="gray">{CATEGORY_LABEL[r.cause_category] ?? r.cause_category}</Badge><span className="text-xs text-slate-500">Chắc chắn {r.confidence_pct}% · {formatDate(r.created_at)}{!r.is_current && " · bản cũ"}</span></div>
                        <ol className="ml-4 list-decimal text-slate-700">{r.whys.map((w, i) => <li key={i}>{w.answer}</li>)}</ol>
                        <p className="mt-1 font-medium">→ {r.root_cause}</p>
                      </div>
                    ))}
                  </CardContent>
                </Card>
              )}

              {["RCA_PENDING", "IN_PROGRESS"].includes(st) && d.rca.some((r) => r.is_current) && <Can perm="feedback.manage"><CapaForm id={id} onDone={onDone} /></Can>}

              {d.capa.length > 0 && (
                <Card data-testid="fb-capa-list">
                  <CardHeader><CardTitle>Hành động CAPA</CardTitle></CardHeader>
                  <CardContent className="space-y-2 text-sm">
                    {d.capa.map((a) => (
                      <div key={a.id} className="rounded-lg border border-slate-100 p-3" data-testid="fb-capa-row">
                        <div className="flex flex-wrap items-center gap-2">
                          <Badge variant={a.action_type === "CORRECTIVE" ? "default" : "purple"}>{a.action_type === "CORRECTIVE" ? "Khắc phục" : "Phòng ngừa"}</Badge>
                          <Badge variant={a.status === "DONE" ? "green" : a.status === "PROPOSED" ? "gray" : "yellow"}>{a.status}</Badge>
                          <span className="flex-1">{a.description}</span>
                          <span className="text-xs text-slate-500">{name(a.owner_id)} · hạn {formatDate(a.deadline, false)}</span>
                          {["IN_PROGRESS", "APPROVED"].includes(a.status) && st === "IN_PROGRESS" && (
                            <Button size="sm" variant="outline" onClick={() => setOpenCapa(openCapa === a.id ? null : a.id)} data-testid="fb-capa-open">Hoàn thành</Button>
                          )}
                          {!["DONE", "CANCELLED"].includes(a.status) && ["RCA_PENDING", "ACTION_APPROVED", "IN_PROGRESS"].includes(st) && (
                            <Can perm="feedback.manage">
                              <Button size="sm" variant="ghost" onClick={() => setOpenCapa(openCapa === `x${a.id}` ? null : `x${a.id}`)} data-testid="fb-capa-cancel-open">Huỷ</Button>
                            </Can>
                          )}
                        </div>
                        {a.completion_evidence.length > 0 && <p className="mt-1 text-xs text-slate-600">Bằng chứng: {a.completion_evidence.map((e) => e.note || e.ref).join("; ")}</p>}
                        {openCapa === a.id && <CompleteCapa capaId={a.id} onDone={onDone} />}
                        {openCapa === `x${a.id}` && <CancelCapa capaId={a.id} onDone={onDone} />}
                      </div>
                    ))}
                    {st === "RCA_PENDING" && (
                      <Can perm="feedback.approve">
                        <div className="pt-2"><p className="mb-1 text-xs text-slate-500">Người lập RCA không được tự phê duyệt CAPA (nguyên tắc 4 mắt).</p>
                          <SimpleAction path={`/feedback/${id}/capa/approve`} label="Phê duyệt CAPA" ok="Đã phê duyệt CAPA" testid="fb-capa-approve" onDone={onDone} variant="success" /></div>
                      </Can>
                    )}
                    {st === "ACTION_APPROVED" && <Can perm="feedback.manage"><SimpleAction path={`/feedback/${id}/start`} label="Giao việc & bắt đầu thực hiện" ok="Đã bắt đầu thực hiện" testid="fb-start" onDone={onDone} /></Can>}
                    {st === "IN_PROGRESS" && <Can perm="feedback.manage"><SimpleAction path={`/feedback/${id}/submit-verification`} label="Gửi kiểm chứng" ok="Đã gửi kiểm chứng" testid="fb-submit-verify" onDone={onDone} /></Can>}
                  </CardContent>
                </Card>
              )}

              {st === "VERIFY_PENDING" && <Can perm="feedback.verify"><VerifyForm id={id} kpiName={c.kpi_name} onDone={onDone} /></Can>}
              {d.verifications.length > 0 && (
                <Card data-testid="fb-verifications">
                  <CardHeader><CardTitle>Kết quả kiểm chứng</CardTitle></CardHeader>
                  <CardContent className="space-y-2 text-sm">
                    {d.verifications.map((v) => (
                      <div key={v.id} className="rounded-lg border border-slate-100 p-2">
                        <Badge variant={v.passed ? "green" : "red"}>{v.passed ? "ĐẠT" : "KHÔNG ĐẠT"}</Badge> {v.method} · KPI {v.kpi_before ?? "—"} → {v.kpi_after ?? "—"} <span className="text-xs text-slate-500">{formatDate(v.created_at)}</span>
                        {v.notes && <p className="text-slate-600">{v.notes}</p>}
                      </div>
                    ))}
                  </CardContent>
                </Card>
              )}
              {st === "VERIFIED" && <Can perm="feedback.close"><StandardizeForm id={id} onDone={onDone} /></Can>}
              {st === "STANDARDIZED" && (
                <Can perm="feedback.close">
                  <Card data-testid="fb-close"><CardHeader><CardTitle>Đóng hồ sơ</CardTitle></CardHeader>
                    <CardContent><SimpleAction path={`/feedback/${id}/close`} label="Đóng hồ sơ" ok="Đã đóng hồ sơ" testid="fb-close-submit" onDone={onDone} /></CardContent></Card>
                </Can>
              )}
              {(d.lessons?.length ?? 0) > 0 ? (
                <p className="text-sm" data-testid="fb-lessons">Bài học M09: {d.lessons!.map((x, i) => (
                  <span key={x.id}>{i > 0 && " · "}<Link className="text-brand-600 hover:underline" href={`/lessons?id=${x.id}`}>{x.code}</Link> ({x.status})</span>
                ))}</p>
              ) : d.lesson_id && <p className="text-sm">Đã tạo bài học: <Link className="text-brand-600 hover:underline" href={`/lessons?id=${d.lesson_id}`}>xem tại M09</Link></p>}

              <Card>
                <CardHeader><CardTitle>Lịch sử</CardTitle></CardHeader>
                <CardContent>
                  <ol className="space-y-2 text-sm" data-testid="fb-events">
                    {[...d.events].reverse().map((e) => (
                      <li key={e.id} className="flex flex-wrap items-center gap-2">
                        <Badge variant="navy">{e.step}</Badge>
                        {e.from_status && <><StatusBadge map={FEEDBACK_STATUS} value={e.from_status} />→</>}
                        <StatusBadge map={FEEDBACK_STATUS} value={e.to_status} />
                        <span className="text-xs text-slate-500">{formatDate(e.created_at)} · {e.actor_type === "USER" ? name(e.actor_ref) : e.actor_ref ?? e.actor_type}</span>
                        <span className="w-full text-slate-600 md:w-auto">{e.note}</span>
                      </li>
                    ))}
                  </ol>
                </CardContent>
              </Card>
            </div>
          );
        }}
      </QueryView>
    </RequirePermission>
  );
}
