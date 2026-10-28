"use client";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { CheckCircle2, Send, Undo2, Wand2, XCircle } from "lucide-react";
import { api } from "@/lib/api";
import { useAction } from "@/hooks/use-mutate";
import { Can } from "@/components/app/require";
import { QueryView } from "@/components/app/states";
import { StatusBadge } from "@/components/app/status-badge";
import { ConfirmButton } from "@/components/app/confirm";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/input";
import { LESSON_STATUS, LESSON_TYPES } from "@/lib/labels";
import { formatDate } from "@/lib/utils";
import type { Lesson } from "@/types/api";

type PV = { id: string; version_no: number; negative_prompt: string; rules: string[]; status: string; change_note: string; template_id: string; created_at: string };

function PromptVersionBox({ id, label }: { id: string; label: string }) {
  const q = useQuery<PV>({ queryKey: ["prompt-version", id], queryFn: () => api(`/prompts/versions/${id}`) });
  return (
    <div className="rounded-lg border border-slate-200 p-2 text-xs" data-testid={`pv-${label}`}>
      <QueryView q={q} rows={1}>
        {(v) => (<>
          <p className="font-semibold">{label}: v{v.version_no} <Badge variant={v.status === "RETIRED" ? "gray" : "green"}>{v.status}</Badge></p>
          <p className="text-slate-500">{v.change_note}</p>
          <p className="mt-1"><b>Negative:</b> {v.negative_prompt || "—"}</p>
          {v.rules.length > 0 && <ul className="ml-4 list-disc">{v.rules.map((r) => <li key={r}>{r}</li>)}</ul>}
        </>)}
      </QueryView>
    </div>
  );
}

export function LessonDetail({ id }: { id: string }) {
  const qc = useQueryClient();
  const q = useQuery<Lesson>({ queryKey: ["lesson", id], queryFn: () => api(`/lessons/${id}`) });
  const [comment, setComment] = useState("");
  const inv = [["lesson", id], ["lessons"]];
  const set = (l: Lesson) => qc.setQueryData(["lesson", id], l);
  const submit = useAction(() => api<Lesson>(`/lessons/${id}/submit`, { method: "POST" }), { success: "Đã gửi duyệt", invalidate: inv, onSuccess: set });
  const review = useAction((approve: boolean) => api<Lesson>(`/lessons/${id}/review`, { body: { approve, comment } }), { success: "Đã ghi nhận duyệt", invalidate: inv, onSuccess: set });
  const apply = useAction(() => api<Lesson>(`/lessons/${id}/apply`, { method: "POST" }), { success: "Đã áp dụng vào prompt chuẩn", invalidate: inv, onSuccess: set });
  return (
    <QueryView q={q}>
      {(l) => (
        <Card data-testid="lesson-detail">
          <CardHeader>
            <p className="font-mono text-xs text-slate-500">{l.code} · v{l.version_no}</p>
            <CardTitle>{l.title}</CardTitle>
            <div className="flex flex-wrap gap-2"><StatusBadge map={LESSON_STATUS} value={l.status} /><Badge variant="gray">{LESSON_TYPES[l.lesson_type] ?? l.lesson_type}</Badge>
              {l.error_category && <Badge variant="gray">{l.error_category}</Badge>}{l.provider_code && <Badge variant="gray">{l.provider_code}</Badge>}</div>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <p className="whitespace-pre-line">{l.lesson}</p>
            {l.root_cause && <p><b>Nguyên nhân gốc:</b> {l.root_cause}</p>}
            {l.capa_summary && <p><b>CAPA:</b> {l.capa_summary}</p>}
            {l.verification_summary && <p><b>Kiểm chứng:</b> {l.verification_summary}</p>}
            {l.prompt_example && <pre className="whitespace-pre-wrap rounded bg-slate-50 p-2 text-xs">{l.prompt_example}</pre>}
            <div className="rounded-lg bg-brand-50 p-2 text-xs" data-testid="lesson-change">
              <p className="font-semibold">Đề xuất thay đổi cấu hình chuẩn</p>
              {l.proposed_change?.template_code ? (<>
                <p>Template: <code>{l.proposed_change.template_code}</code></p>
                {l.proposed_change.append_negative && <p>+ Negative: {l.proposed_change.append_negative}</p>}
                {l.proposed_change.append_rule && <p>+ Quy tắc: {l.proposed_change.append_rule}</p>}
              </>) : <p>Không có (bài học tham khảo)</p>}
              <p className="mt-1 text-brand-700">Chỉ áp dụng vào cấu hình chuẩn sau khi bài học được duyệt. Mọi lần áp dụng tạo phiên bản prompt mới và có thể rollback.</p>
            </div>
            {(l.previous_prompt_version_id || l.applied_prompt_version_id) && (
              <div className="grid gap-2 md:grid-cols-2">
                {l.previous_prompt_version_id && <PromptVersionBox id={l.previous_prompt_version_id} label="Trước" />}
                {l.applied_prompt_version_id && <PromptVersionBox id={l.applied_prompt_version_id} label="Sau" />}
              </div>
            )}
            <p className="text-xs text-slate-500">Tạo {formatDate(l.created_at)} · Duyệt {formatDate(l.approved_at)} · Áp dụng {formatDate(l.applied_at)}{l.rolled_back_at && ` · Rollback ${formatDate(l.rolled_back_at)}`}</p>
            {l.feedback_case_id && <a className="text-xs text-brand-600 hover:underline" href={`/feedback/${l.feedback_case_id}`}>Hồ sơ Feedback gốc</a>}

            <div className="flex flex-wrap gap-2 border-t border-slate-100 pt-3">
              {["DRAFT", "REJECTED"].includes(l.status) && <Can perm="lesson.create"><Button size="sm" onClick={() => submit.mutate(undefined)} loading={submit.isPending} data-testid="lesson-submit"><Send />Gửi duyệt</Button></Can>}
              {l.status === "PENDING_APPROVAL" && (
                <Can perm="lesson.approve">
                  <div className="w-full space-y-2">
                    <Textarea placeholder="Nhận xét (bắt buộc khi từ chối)" value={comment} onChange={(e) => setComment(e.target.value)} data-testid="lesson-comment" />
                    <div className="flex gap-2">
                      <Button size="sm" variant="success" onClick={() => review.mutate(true)} loading={review.isPending} data-testid="lesson-approve"><CheckCircle2 />Duyệt</Button>
                      <Button size="sm" variant="destructive" disabled={comment.trim().length < 3} onClick={() => review.mutate(false)} data-testid="lesson-reject"><XCircle />Từ chối</Button>
                    </div>
                  </div>
                </Can>
              )}
              {l.status === "APPROVED" && l.proposed_change?.template_code && <Can perm="lesson.apply"><Button size="sm" onClick={() => apply.mutate(undefined)} loading={apply.isPending} data-testid="lesson-apply"><Wand2 />Áp dụng vào prompt chuẩn</Button></Can>}
              {l.status === "APPLIED" && (
                <Can perm="lesson.apply">
                  <ConfirmButton size="sm" variant="outline" title="Rollback bài học?" description="Prompt chuẩn sẽ quay về phiên bản trước khi áp dụng." requireReason data-testid="lesson-rollback"
                    onConfirm={async (reason) => { const r = await api<Lesson>(`/lessons/${id}/rollback`, { body: { reason } }); set(r); qc.invalidateQueries({ queryKey: ["lessons"] }); }}>
                    <Undo2 />Rollback
                  </ConfirmButton>
                </Can>
              )}
            </div>
            {l.history.length > 0 && (
              <details className="text-xs"><summary className="cursor-pointer text-slate-500">Lịch sử phiên bản ({l.history.length})</summary>
                <ul className="mt-1 space-y-1">{l.history.map((h, i) => <li key={i} className="rounded bg-slate-50 p-1">{JSON.stringify({ ...h, data: undefined })}</li>)}</ul>
              </details>
            )}
          </CardContent>
        </Card>
      )}
    </QueryView>
  );
}
