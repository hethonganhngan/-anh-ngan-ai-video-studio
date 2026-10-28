"use client";
import Link from "next/link";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle } from "lucide-react";
import { Area, AreaChart, Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "@/lib/api";
import { useChannels, useUsers } from "@/hooks/use-lookups";
import { useAuth } from "@/hooks/use-auth";
import { PageHeader } from "@/components/app/page-header";
import { RequirePermission } from "@/components/app/require";
import { EmptyState, QueryView } from "@/components/app/states";
import { KpiCard } from "@/components/app/kpi-card";
import { StatusBadge } from "@/components/app/status-badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, NativeSelect } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { PROJECT_STATUS } from "@/lib/labels";
import { formatNumber, formatVND } from "@/lib/utils";
import type { Kpi, Page, Project } from "@/types/api";

type Dash = {
  mode: string; period: { from: string; to: string }; kpis: Kpi[]; by_status: Record<string, number>;
  series: { date: string; created: number; approved: number; published: number; cost: number }[];
  top_videos: { publication_id: string; project_id: string; project_code: string; title: string; platform: string; views: number; engagement_rate: number | null; cost: number; cost_per_1k_views: number | null }[];
  budget_alerts: { scope: string; ref: string; period: string; used: number; limit: number; pct: number; level: string }[];
  simulated_cost: number;
};

/** Ngày theo giờ địa phương (không dùng toISOString — lệch ngày theo UTC). */
const iso = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;

export default function DashboardPage() {
  const { me } = useAuth();
  const channels = useChannels();
  const users = useUsers();
  const projects = useQuery<Page<Project>>({ queryKey: ["projects", "dash-filter"], queryFn: () => api("/projects?page_size=200") });
  const today = new Date();
  const [from, setFrom] = useState(iso(new Date(today.getTime() - 29 * 86400000)));
  const [to, setTo] = useState(iso(today));
  const [channel, setChannel] = useState("");
  const [project, setProject] = useState("");
  const [owner, setOwner] = useState("");
  const params = new URLSearchParams();
  if (from) params.set("date_from", `${from}T00:00:00+07:00`);
  if (to) params.set("date_to", `${to}T23:59:59+07:00`);
  if (channel) params.set("channel_id", channel);
  if (project) params.set("project_id", project);
  if (owner) params.set("owner_id", owner);
  const q = useQuery<Dash>({ queryKey: ["dashboard", params.toString()], queryFn: () => api(`/dashboard?${params}`) });

  return (
    <RequirePermission perm="dashboard.view">
      <PageHeader code="M01" title="Dashboard CEO" description="Toàn cảnh sản xuất, chất lượng, chi phí và hiệu quả video. Bấm biểu tượng (i) để xem công thức & nguồn dữ liệu." />
      <Card className="mb-4">
        <CardContent className="grid gap-3 pt-5 md:grid-cols-5">
          <div><Label>Từ ngày</Label><Input type="date" value={from} onChange={(e) => setFrom(e.target.value)} data-testid="dash-from" /></div>
          <div><Label>Đến ngày</Label><Input type="date" value={to} onChange={(e) => setTo(e.target.value)} data-testid="dash-to" /></div>
          <div><Label>Kênh</Label>
            <NativeSelect value={channel} onChange={(e) => setChannel(e.target.value)} data-testid="dash-channel">
              <option value="">Tất cả kênh</option>
              {(channels.data ?? []).map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </NativeSelect></div>
          <div><Label>Dự án</Label>
            <NativeSelect value={project} onChange={(e) => setProject(e.target.value)} data-testid="dash-project">
              <option value="">Tất cả dự án</option>
              {(projects.data?.items ?? []).map((p) => <option key={p.id} value={p.id}>{p.code} · {p.title.slice(0, 40)}</option>)}
            </NativeSelect></div>
          <div><Label>Người phụ trách</Label>
            <NativeSelect value={owner} onChange={(e) => setOwner(e.target.value)} data-testid="dash-owner">
              <option value="">Tất cả</option>
              {(users.data ?? []).map((u) => <option key={u.id} value={u.id}>{u.full_name}</option>)}
            </NativeSelect></div>
        </CardContent>
      </Card>
      <QueryView q={q} rows={6}>
        {(d) => (
          <div className="space-y-4">
            {d.mode === "DEMO" && d.simulated_cost > 0 && (
              <p className="rounded-lg border border-amber-200 bg-amber-50 p-2 text-sm text-amber-800" data-testid="simulated-note">
                Chế độ DEMO: {formatVND(d.simulated_cost)} chi phí là <b>MÔ PHỎNG</b> (Mock Provider), không phải chi phí thật.
              </p>
            )}
            {d.budget_alerts.length > 0 && (
              <Card className="border-red-200" data-testid="budget-alerts">
                <CardHeader><CardTitle className="flex items-center gap-2 text-red-700"><AlertTriangle className="h-4 w-4" />Cảnh báo ngân sách</CardTitle></CardHeader>
                <CardContent className="space-y-1">
                  {d.budget_alerts.map((a, i) => (
                    <div key={i} className="flex flex-wrap items-center justify-between gap-2 text-sm">
                      <span><Badge variant={a.level === "CRITICAL" ? "red" : "yellow"}>{a.level === "CRITICAL" ? "Vượt" : "Sắp chạm"}</Badge> {a.scope} {a.ref !== "*" ? a.ref : ""} ({a.period})</span>
                      <span>{formatVND(a.used)} / {formatVND(a.limit)} · <b>{a.pct}%</b></span>
                    </div>
                  ))}
                </CardContent>
              </Card>
            )}
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-5" data-testid="kpi-grid">
              {d.kpis.map((k) => <KpiCard key={k.key} kpi={k} />)}
            </div>
            <div className="grid gap-4 lg:grid-cols-2">
              <Card>
                <CardHeader><CardTitle>Video theo ngày</CardTitle></CardHeader>
                <CardContent className="h-64" data-testid="chart-videos">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={d.series}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                      <XAxis dataKey="date" tickFormatter={(v: string) => v.slice(5)} fontSize={11} />
                      <YAxis allowDecimals={false} fontSize={11} />
                      <Tooltip />
                      <Legend />
                      <Line type="monotone" dataKey="created" name="Tạo mới" stroke="#2563eb" dot={false} />
                      <Line type="monotone" dataKey="approved" name="Đã duyệt" stroke="#059669" dot={false} />
                      <Line type="monotone" dataKey="published" name="Đã đăng" stroke="#f59e0b" dot={false} />
                    </LineChart>
                  </ResponsiveContainer>
                </CardContent>
              </Card>
              <Card>
                <CardHeader><CardTitle>Chi phí theo ngày (VND)</CardTitle></CardHeader>
                <CardContent className="h-64" data-testid="chart-cost">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={d.series}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                      <XAxis dataKey="date" tickFormatter={(v: string) => v.slice(5)} fontSize={11} />
                      <YAxis fontSize={11} tickFormatter={(v: number) => formatNumber(v)} />
                      <Tooltip formatter={(v: number) => formatVND(v)} />
                      <Area type="monotone" dataKey="cost" name="Chi phí" stroke="#1d4ed8" fill="#dbeafe" />
                    </AreaChart>
                  </ResponsiveContainer>
                </CardContent>
              </Card>
              <Card>
                <CardHeader><CardTitle>Phân bố trạng thái dự án</CardTitle></CardHeader>
                <CardContent className="h-64" data-testid="chart-status">
                  {Object.keys(d.by_status).length === 0 ? <EmptyState title="Chưa có dự án" /> : (
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={Object.entries(d.by_status).map(([k, v]) => ({ name: PROJECT_STATUS[k]?.label ?? k, value: v }))} layout="vertical" margin={{ left: 40 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                        <XAxis type="number" allowDecimals={false} fontSize={11} />
                        <YAxis type="category" dataKey="name" width={130} fontSize={11} />
                        <Tooltip />
                        <Bar dataKey="value" name="Số dự án" fill="#3b82f6" radius={[0, 4, 4, 0]} />
                      </BarChart>
                    </ResponsiveContainer>
                  )}
                </CardContent>
              </Card>
              <Card>
                <CardHeader><CardTitle>Top video (lượt xem)</CardTitle></CardHeader>
                <CardContent>
                  {d.top_videos.length === 0 ? <EmptyState title="Chưa có video đã đăng" description="Số liệu xuất hiện sau khi nhập analytics tại M10." /> : (
                    <Table data-testid="top-videos">
                      <THead><TR><TH>Video</TH><TH>Nền tảng</TH><TH>Lượt xem</TH><TH>Tương tác</TH><TH>Chi phí/1K view</TH></TR></THead>
                      <TBody>
                        {d.top_videos.map((v) => (
                          <TR key={v.publication_id}>
                            <TD><Link className="text-brand-600 hover:underline" href={`/projects/${v.project_id}`}>{v.project_code}</Link> <span className="text-xs text-slate-500">{v.title.slice(0, 30)}</span></TD>
                            <TD>{v.platform}</TD>
                            <TD>{formatNumber(v.views)}</TD>
                            <TD>{v.engagement_rate === null ? "—" : `${v.engagement_rate}%`}</TD>
                            <TD>{v.cost_per_1k_views === null ? "—" : formatVND(v.cost_per_1k_views)}</TD>
                          </TR>
                        ))}
                      </TBody>
                    </Table>
                  )}
                </CardContent>
              </Card>
            </div>
            <p className="text-xs text-slate-400">Kỳ: {d.period.from.slice(0, 10)} → {d.period.to.slice(0, 10)} · Chế độ {d.mode} · Người xem: {me?.full_name}</p>
            <div className="flex flex-wrap gap-2">
              {Object.entries(d.by_status).map(([k, v]) => <span key={k} className="flex items-center gap-1 text-xs"><StatusBadge map={PROJECT_STATUS} value={k} />{v}</span>)}
            </div>
            <Button variant="outline" asChild><Link href="/projects">Xem danh sách dự án</Link></Button>
          </div>
        )}
      </QueryView>
    </RequirePermission>
  );
}
