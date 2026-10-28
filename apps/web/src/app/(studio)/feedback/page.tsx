"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { api } from "@/lib/api";
import { useAction } from "@/hooks/use-mutate";
import { PageHeader } from "@/components/app/page-header";
import { RequirePermission, Can } from "@/components/app/require";
import { EmptyState, QueryView } from "@/components/app/states";
import { StatusBadge } from "@/components/app/status-badge";
import { ProjectPicker } from "@/components/app/project-picker";
import { Field } from "@/components/app/field";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input, NativeSelect, Textarea } from "@/components/ui/input";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { FEEDBACK_STATUS, PRIORITY } from "@/lib/labels";
import { formatDate } from "@/lib/utils";
import { CATEGORY_LABEL, EVIDENCE_LABEL, SOURCE_LABEL, type FeedbackDetail, type FeedbackMeta } from "@/features/feedback/types";
import { EvidenceEditor, cleanEv, emptyEv, type Ev } from "@/features/feedback/evidence-editor";
import type { FeedbackCase, Page } from "@/types/api";

type Stats = { by_status: Record<string, number>; total: number; capa_verified_rate: number | null; overdue: number; formula: string };

function CreateDialog({ meta, open, onOpenChange }: { meta?: FeedbackMeta; open: boolean; onOpenChange: (o: boolean) => void }) {
  const router = useRouter();
  const [f, setF] = useState({ source: "INTERNAL", category: "OTHER", title: "", description: "", evidence_class: "UNKNOWN" });
  const [project, setProject] = useState<string | null>(null);
  const [ev, setEv] = useState<Ev[]>([emptyEv()]);
  const create = useAction((body: unknown) => api<FeedbackDetail>("/feedback", { body }),
    { success: (r) => `Đã tạo hồ sơ ${r.case.code}`, invalidate: [["feedback"]], onSuccess: (r) => { onOpenChange(false); router.push(`/feedback/${r.case.id}`); } });
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent wide>
        <DialogHeader><DialogTitle>Tạo hồ sơ phản hồi (INTAKE)</DialogTitle></DialogHeader>
        <div className="grid gap-3 md:grid-cols-2">
          <Field label="Nguồn phản hồi">
            <NativeSelect value={f.source} onChange={(e) => setF({ ...f, source: e.target.value })} data-testid="fb-source">
              {(meta?.sources ?? Object.keys(SOURCE_LABEL)).map((s) => <option key={s} value={s}>{SOURCE_LABEL[s] ?? s}</option>)}
            </NativeSelect>
          </Field>
          <Field label="Loại lỗi">
            <NativeSelect value={f.category} onChange={(e) => setF({ ...f, category: e.target.value })} data-testid="fb-category">
              {(meta?.categories ?? Object.keys(CATEGORY_LABEL)).map((s) => <option key={s} value={s}>{CATEGORY_LABEL[s] ?? s}</option>)}
            </NativeSelect>
          </Field>
          <Field label="Tiêu đề" className="space-y-1 md:col-span-2"><Input value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} data-testid="fb-title" /></Field>
          <Field label="Mô tả" className="space-y-1 md:col-span-2"><Textarea value={f.description} onChange={(e) => setF({ ...f, description: e.target.value })} data-testid="fb-desc" /></Field>
          <Field label="Video liên quan (tuỳ chọn)" className="space-y-1 md:col-span-2"><ProjectPicker value={project} onChange={setProject} className="w-full" /></Field>
          <Field label="Phân loại bằng chứng">
            <NativeSelect value={f.evidence_class} onChange={(e) => setF({ ...f, evidence_class: e.target.value })} data-testid="fb-class">
              {Object.entries(EVIDENCE_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </NativeSelect>
          </Field>
        </div>
        <div className="mt-3"><p className="mb-1 text-sm font-medium">Bằng chứng</p><EvidenceEditor value={ev} onChange={setEv} testid="fb-evidence" /></div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>Huỷ</Button>
          <Button disabled={f.title.trim().length < 3} loading={create.isPending} data-testid="fb-create-submit"
            onClick={() => create.mutate({ ...f, project_id: project, evidence: cleanEv(ev) })}>Tạo hồ sơ</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export default function FeedbackPage() {
  const [status, setStatus] = useState("");
  const [priority, setPriority] = useState("");
  const [source, setSource] = useState("");
  const [category, setCategory] = useState("");
  const [qtext, setQtext] = useState("");
  const [open, setOpen] = useState(false);
  const meta = useQuery<FeedbackMeta>({ queryKey: ["feedback-meta"], queryFn: () => api("/feedback/meta") });
  const stats = useQuery<Stats>({ queryKey: ["feedback", "stats"], queryFn: () => api("/feedback/stats") });
  const p = new URLSearchParams({ page_size: "200" });
  if (status) p.set("status", status);
  if (priority) p.set("priority", priority);
  if (source) p.set("source", source);
  if (category) p.set("category", category);
  if (qtext) p.set("q", qtext);
  const list = useQuery<Page<FeedbackCase>>({ queryKey: ["feedback", p.toString()], queryFn: () => api(`/feedback?${p}`) });
  const now = Date.now();
  return (
    <RequirePermission perm="feedback.view">
      <PageHeader code="M08" title="Feedback Loop 360°" description="INTAKE → VALIDATE → TRIAGE → ROOT CAUSE → CAPA → ASSIGN → VERIFY → STANDARDIZE. Không đóng hồ sơ khi thiếu bằng chứng."
        actions={<Can perm="feedback.create"><Button onClick={() => setOpen(true)} data-testid="fb-new"><Plus />Tạo hồ sơ</Button></Can>} />
      <div className="mb-4 grid gap-3 md:grid-cols-4" data-testid="fb-stats">
        <Card className="p-4"><p className="text-xs uppercase text-slate-500">Tổng hồ sơ</p><p className="text-2xl font-bold">{stats.data?.total ?? "—"}</p></Card>
        <Card className="p-4"><p className="text-xs uppercase text-slate-500">Đang mở</p><p className="text-2xl font-bold">{stats.data ? stats.data.total - (stats.data.by_status.CLOSED ?? 0) : "—"}</p></Card>
        <Card className="p-4"><p className="text-xs uppercase text-slate-500">Quá hạn</p><p className="text-2xl font-bold text-red-600">{stats.data?.overdue ?? "—"}</p></Card>
        <Card className="p-4" title={stats.data?.formula}><p className="text-xs uppercase text-slate-500">Tỷ lệ CAPA được xác minh</p><p className="text-2xl font-bold">{stats.data?.capa_verified_rate ?? "—"}{stats.data?.capa_verified_rate != null && "%"}</p></Card>
      </div>
      <Card>
        <CardContent className="space-y-4 pt-5">
          <div className="grid gap-2 md:grid-cols-5">
            <Input placeholder="Tìm mã, tiêu đề…" value={qtext} onChange={(e) => setQtext(e.target.value)} data-testid="fb-filter-q" />
            <NativeSelect value={status} onChange={(e) => setStatus(e.target.value)} data-testid="fb-filter-status">
              <option value="">Mọi trạng thái</option>
              {Object.entries(FEEDBACK_STATUS).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
            </NativeSelect>
            <NativeSelect value={priority} onChange={(e) => setPriority(e.target.value)}><option value="">Mọi ưu tiên</option>{["P0", "P1", "P2", "P3"].map((x) => <option key={x}>{x}</option>)}</NativeSelect>
            <NativeSelect value={source} onChange={(e) => setSource(e.target.value)}><option value="">Mọi nguồn</option>{Object.entries(SOURCE_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</NativeSelect>
            <NativeSelect value={category} onChange={(e) => setCategory(e.target.value)}><option value="">Mọi loại lỗi</option>{Object.entries(CATEGORY_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</NativeSelect>
          </div>
          <QueryView q={list} isEmpty={(d) => d.items.length === 0} empty={<EmptyState title="Chưa có hồ sơ phản hồi" description="Hồ sơ được tạo từ lỗi QC, khách hàng, số liệu hoặc nội bộ." />}>
            {(d) => (
              <Table data-testid="fb-table">
                <THead><TR><TH>Mã</TH><TH>Tiêu đề</TH><TH>Nguồn</TH><TH>Loại</TH><TH>Ưu tiên</TH><TH>Trạng thái</TH><TH>Deadline</TH><TH>Tạo lúc</TH></TR></THead>
                <TBody>
                  {d.items.map((c) => {
                    const overdue = c.deadline && new Date(c.deadline).getTime() < now && !["VERIFIED", "STANDARDIZED", "CLOSED"].includes(c.status);
                    return (
                      <TR key={c.id} data-testid="fb-row">
                        <TD className="font-mono text-xs"><Link className="text-brand-600 hover:underline" href={`/feedback/${c.id}`}>{c.code}</Link></TD>
                        <TD className="max-w-xs truncate">{c.title}</TD>
                        <TD>{SOURCE_LABEL[c.source] ?? c.source}</TD>
                        <TD>{CATEGORY_LABEL[c.category] ?? c.category}</TD>
                        <TD>{c.priority ? <Badge variant={PRIORITY[c.priority]}>{c.priority}</Badge> : "—"}</TD>
                        <TD><StatusBadge map={FEEDBACK_STATUS} value={c.status} /></TD>
                        <TD className={overdue ? "text-xs font-medium text-red-600" : "text-xs"}>{formatDate(c.deadline, false)}{overdue && " · quá hạn"}</TD>
                        <TD className="text-xs">{formatDate(c.created_at)}</TD>
                      </TR>
                    );
                  })}
                </TBody>
              </Table>
            )}
          </QueryView>
        </CardContent>
      </Card>
      <CreateDialog meta={meta.data} open={open} onOpenChange={setOpen} />
    </RequirePermission>
  );
}
