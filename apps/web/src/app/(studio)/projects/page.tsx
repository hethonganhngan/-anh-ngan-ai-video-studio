"use client";
import Link from "next/link";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Plus, RefreshCw, RotateCcw, XCircle } from "lucide-react";
import { api } from "@/lib/api";
import { useAction } from "@/hooks/use-mutate";
import { useChannels, useUsers } from "@/hooks/use-lookups";
import { PageHeader } from "@/components/app/page-header";
import { RequirePermission, Can } from "@/components/app/require";
import { EmptyState, QueryView } from "@/components/app/states";
import { StatusBadge } from "@/components/app/status-badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, NativeSelect } from "@/components/ui/input";
import { Progress } from "@/components/ui/misc";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { JOB_STATUS, PROJECT_STATUS } from "@/lib/labels";
import { formatDate, formatVND } from "@/lib/utils";
import type { GenerationJob, Page, Project } from "@/types/api";

type Kanban = { columns: { name: string; statuses: string[]; items: Project[] }[] };
type RenderJob = { id: string; project_id: string; status: string; attempt_no: number; max_retries: number; error_message: string | null; created_at: string; finished_at: string | null };

function ProjectsTable() {
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const [channel, setChannel] = useState("");
  const [owner, setOwner] = useState("");
  const channels = useChannels();
  const users = useUsers();
  const params = new URLSearchParams({ page_size: "200" });
  if (q) params.set("q", q);
  if (status) params.set("status", status);
  if (channel) params.set("channel_id", channel);
  if (owner) params.set("owner_id", owner);
  const list = useQuery<Page<Project>>({ queryKey: ["projects", params.toString()], queryFn: () => api(`/projects?${params}`) });
  const userName = (id: string | null) => users.data?.find((u) => u.id === id)?.full_name ?? "—";
  return (
    <Card>
      <CardContent className="space-y-4 pt-5">
        <div className="grid gap-2 md:grid-cols-4">
          <Input placeholder="Tìm mã, tiêu đề, chủ đề…" value={q} onChange={(e) => setQ(e.target.value)} data-testid="filter-q" />
          <NativeSelect value={status} onChange={(e) => setStatus(e.target.value)} data-testid="filter-status">
            <option value="">Mọi trạng thái</option>
            {Object.entries(PROJECT_STATUS).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
          </NativeSelect>
          <NativeSelect value={channel} onChange={(e) => setChannel(e.target.value)} data-testid="filter-channel">
            <option value="">Mọi kênh</option>
            {(channels.data ?? []).map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </NativeSelect>
          <NativeSelect value={owner} onChange={(e) => setOwner(e.target.value)} data-testid="filter-owner">
            <option value="">Mọi người phụ trách</option>
            {(users.data ?? []).map((u) => <option key={u.id} value={u.id}>{u.full_name}</option>)}
          </NativeSelect>
        </div>
        <QueryView q={list} isEmpty={(d) => d.items.length === 0}
          empty={<EmptyState title="Chưa có dự án" description="Tạo video đầu tiên tại M02 — Trung tâm tạo video." action={<Can perm="project.create"><Button asChild><Link href="/create"><Plus />Tạo video</Link></Button></Can>} />}>
          {(d) => (
            <Table data-testid="projects-table">
              <THead><TR><TH>Mã</TH><TH>Tiêu đề</TH><TH>Kênh</TH><TH>Trạng thái</TH><TH className="w-40">Tiến độ</TH><TH>Phụ trách</TH><TH>Deadline</TH><TH>Ngân sách</TH></TR></THead>
              <TBody>
                {d.items.map((p) => (
                  <TR key={p.id} data-testid="project-row">
                    <TD className="font-mono text-xs"><Link className="text-brand-600 hover:underline" href={`/projects/${p.id}`}>{p.code}</Link>{p.data_mode === "DEMO" && <span className="ml-1 rounded bg-amber-100 px-1 text-[10px] text-amber-800">DEMO</span>}</TD>
                    <TD className="max-w-xs truncate">{p.title}</TD>
                    <TD>{p.channel.name}</TD>
                    <TD><StatusBadge map={PROJECT_STATUS} value={p.status} /></TD>
                    <TD><Progress value={p.progress} /><span className="text-[11px] text-slate-500">{p.progress}%</span></TD>
                    <TD>{userName(p.owner_id)}</TD>
                    <TD>{formatDate(p.deadline, false)}</TD>
                    <TD>{Number(p.budget_limit) > 0 ? formatVND(p.budget_limit) : "—"}</TD>
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

function KanbanBoard() {
  const q = useQuery<Kanban>({ queryKey: ["projects", "kanban"], queryFn: () => api("/projects/kanban") });
  return (
    <QueryView q={q}>
      {(d) => (
        <div className="grid gap-3 md:grid-cols-3 xl:grid-cols-6" data-testid="kanban">
          {d.columns.map((c) => (
            <div key={c.name} className="rounded-xl bg-slate-100 p-2" data-testid="kanban-column">
              <p className="mb-2 flex items-center justify-between px-1 text-xs font-semibold text-slate-600">{c.name}<span className="rounded-full bg-white px-2">{c.items.length}</span></p>
              <div className="space-y-2">
                {c.items.map((p) => (
                  <Link key={p.id} href={`/projects/${p.id}`} className="block rounded-lg bg-white p-2 text-sm shadow-sm hover:ring-2 hover:ring-brand-500" data-testid="kanban-card">
                    <p className="font-mono text-[11px] text-slate-500">{p.code}</p>
                    <p className="line-clamp-2 font-medium">{p.title}</p>
                    <div className="mt-1"><StatusBadge map={PROJECT_STATUS} value={p.status} /></div>
                  </Link>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </QueryView>
  );
}

function QueueView() {
  const [status, setStatus] = useState("");
  const jobs = useQuery<Page<GenerationJob>>({ queryKey: ["jobs", status], queryFn: () => api(`/generation-jobs?page_size=200${status ? `&status=${status}` : ""}`), refetchInterval: 5000 });
  const renders = useQuery<RenderJob[]>({ queryKey: ["render-jobs"], queryFn: () => api("/render-jobs"), refetchInterval: 5000 });
  const cancel = useAction((id: string) => api(`/generation-jobs/${id}/cancel`, { method: "POST" }), { success: "Đã huỷ tác vụ", invalidate: [["jobs"]] });
  const regen = useAction((sceneId: string) => api(`/scenes/${sceneId}/regenerate`, { method: "POST" }), { success: "Đã xếp hàng tạo lại", invalidate: [["jobs"]] });
  const recover = useAction(() => api<{ generation: number; render: number }>("/jobs/recover", { method: "POST" }),
    { success: (r) => `Đã gửi lại ${r.generation} tác vụ tạo cảnh, ${r.render} tác vụ render`, invalidate: [["jobs"], ["render-jobs"]] });
  return (
    <div className="space-y-4">
      <Card>
        <CardHeader className="flex-row items-center justify-between">
          <CardTitle>Hàng đợi tạo cảnh</CardTitle>
          <div className="flex gap-2">
            <NativeSelect className="w-48" value={status} onChange={(e) => setStatus(e.target.value)} data-testid="queue-status">
              <option value="">Mọi trạng thái</option>
              {Object.entries(JOB_STATUS).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
            </NativeSelect>
            <Can perm="generation.run"><Button variant="outline" onClick={() => recover.mutate(undefined)} loading={recover.isPending} data-testid="recover-jobs"><RefreshCw />Khôi phục tác vụ kẹt</Button></Can>
          </div>
        </CardHeader>
        <CardContent>
          <QueryView q={jobs} isEmpty={(d) => d.items.length === 0} empty={<EmptyState title="Hàng đợi trống" />}>
            {(d) => (
              <Table data-testid="jobs-table">
                <THead><TR><TH>Job</TH><TH>Provider</TH><TH>Trạng thái</TH><TH>Lần</TH><TH>Chi phí</TH><TH>Lỗi</TH><TH>Tạo lúc</TH><TH></TH></TR></THead>
                <TBody>
                  {d.items.map((j) => (
                    <TR key={j.id} data-testid="job-row">
                      <TD className="font-mono text-xs"><Link className="text-brand-600 hover:underline" href={`/production?project=${j.project_id}`}>{j.id.slice(0, 8)}</Link></TD>
                      <TD>{j.provider_code}</TD>
                      <TD><StatusBadge map={JOB_STATUS} value={j.status} /></TD>
                      <TD>{j.attempt_no}/{j.max_retries + 1}</TD>
                      <TD>{formatVND(j.actual_cost || j.estimated_cost)}</TD>
                      <TD className="max-w-xs truncate text-xs text-red-700" title={j.error_message ?? ""}>{j.error_message ?? ""}</TD>
                      <TD className="text-xs">{formatDate(j.created_at)}</TD>
                      <TD className="space-x-1 text-right">
                        {["QUEUED", "SUBMITTED", "RUNNING", "NEEDS_MANUAL_ACTION"].includes(j.status) && (
                          <Can perm="generation.cancel"><Button size="sm" variant="ghost" onClick={() => cancel.mutate(j.id)} data-testid="job-cancel"><XCircle />Huỷ</Button></Can>
                        )}
                        {["FAILED", "CANCELLED", "BLOCKED_BUDGET"].includes(j.status) && (
                          <Can perm="generation.run"><Button size="sm" variant="ghost" onClick={() => regen.mutate(j.scene_id)} data-testid="job-retry"><RotateCcw />Retry</Button></Can>
                        )}
                      </TD>
                    </TR>
                  ))}
                </TBody>
              </Table>
            )}
          </QueryView>
        </CardContent>
      </Card>
      <Card>
        <CardHeader><CardTitle>Hàng đợi render</CardTitle></CardHeader>
        <CardContent>
          <QueryView q={renders} isEmpty={(d) => d.length === 0} empty={<EmptyState title="Chưa có tác vụ render" />}>
            {(d) => (
              <Table>
                <THead><TR><TH>Job</TH><TH>Trạng thái</TH><TH>Lần</TH><TH>Lỗi</TH><TH>Tạo lúc</TH><TH>Xong lúc</TH></TR></THead>
                <TBody>
                  {d.map((j) => (
                    <TR key={j.id}>
                      <TD className="font-mono text-xs"><Link className="text-brand-600 hover:underline" href={`/projects/${j.project_id}`}>{j.id.slice(0, 8)}</Link></TD>
                      <TD><StatusBadge map={JOB_STATUS} value={j.status} /></TD>
                      <TD>{j.attempt_no}/{j.max_retries + 1}</TD>
                      <TD className="max-w-xs truncate text-xs text-red-700">{j.error_message ?? ""}</TD>
                      <TD className="text-xs">{formatDate(j.created_at)}</TD>
                      <TD className="text-xs">{formatDate(j.finished_at)}</TD>
                    </TR>
                  ))}
                </TBody>
              </Table>
            )}
          </QueryView>
        </CardContent>
      </Card>
    </div>
  );
}

function Batches() {
  const list = useQuery<Page<Project>>({ queryKey: ["projects", "batches"], queryFn: () => api("/projects?page_size=200") });
  return (
    <QueryView q={list}>
      {(d) => {
        const groups = new Map<string, Project[]>();
        d.items.filter((p) => p.batch_id).forEach((p) => groups.set(p.batch_id!, [...(groups.get(p.batch_id!) ?? []), p]));
        if (!groups.size) return <EmptyState title="Chưa có lô sản xuất" description="Tạo nhiều video cùng lúc tại M02 với Số lượng > 1." />;
        return (
          <div className="grid gap-3 md:grid-cols-2" data-testid="batches">
            {[...groups.entries()].map(([bid, items]) => {
              const done = items.filter((p) => ["APPROVED", "PUBLISH_QUEUED", "PUBLISHED", "ANALYTICS_COLLECTION", "FEEDBACK_REVIEW"].includes(p.status)).length;
              return (
                <Card key={bid} data-testid="batch-card">
                  <CardHeader><CardTitle className="text-sm">Lô {bid.slice(0, 8)} · {items.length} video</CardTitle></CardHeader>
                  <CardContent className="space-y-2">
                    <Progress value={(done / items.length) * 100} />
                    {items.map((p) => (
                      <div key={p.id} className="flex items-center justify-between text-sm">
                        <Link href={`/projects/${p.id}`} className="truncate text-brand-600 hover:underline">{p.code} · {p.title}</Link>
                        <StatusBadge map={PROJECT_STATUS} value={p.status} />
                      </div>
                    ))}
                  </CardContent>
                </Card>
              );
            })}
          </div>
        );
      }}
    </QueryView>
  );
}

export default function ProjectsPage() {
  return (
    <RequirePermission perm="project.view">
      <PageHeader code="M11" title="Quản lý dự án & hàng đợi" description="Theo dõi tiến độ, Kanban, hàng đợi tác vụ, lô sản xuất và nhật ký thực thi."
        actions={<Can perm="project.create"><Button asChild data-testid="new-project"><Link href="/create"><Plus />Tạo video</Link></Button></Can>} />
      <Tabs defaultValue="list">
        <TabsList>
          <TabsTrigger value="list">Danh sách</TabsTrigger>
          <TabsTrigger value="kanban" data-testid="tab-kanban">Kanban</TabsTrigger>
          <TabsTrigger value="queue" data-testid="tab-queue">Hàng đợi</TabsTrigger>
          <TabsTrigger value="batches" data-testid="tab-batches">Lô sản xuất</TabsTrigger>
        </TabsList>
        <TabsContent value="list"><ProjectsTable /></TabsContent>
        <TabsContent value="kanban"><KanbanBoard /></TabsContent>
        <TabsContent value="queue"><QueueView /></TabsContent>
        <TabsContent value="batches"><Batches /></TabsContent>
      </Tabs>
    </RequirePermission>
  );
}
