"use client";
import Link from "next/link";
import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { CalendarPlus, Info, Wand2 } from "lucide-react";
import { api } from "@/lib/api";
import { useAction } from "@/hooks/use-mutate";
import { PageHeader } from "@/components/app/page-header";
import { RequirePermission, Can } from "@/components/app/require";
import { EmptyState, QueryView } from "@/components/app/states";
import { StatusBadge } from "@/components/app/status-badge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { NativeSelect } from "@/components/ui/input";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { PROJECT_STATUS, PUB_STATUS } from "@/lib/labels";
import { formatDate } from "@/lib/utils";
import { PublishCalendar } from "@/features/publishing/calendar";
import { CreatePublication } from "@/features/publishing/create-pub";
import { PubRowActions } from "@/features/publishing/pub-actions";
import { AnalyticsPanel } from "@/features/publishing/analytics";
import { PLATFORM_LABEL, type ChannelFull } from "@/features/publishing/types";
import type { Project, Publication } from "@/types/api";

export default function PublishingPage() {
  const [channel, setChannel] = useState("");
  const [creating, setCreating] = useState<Project | null>(null);
  const channels = useQuery<ChannelFull[]>({ queryKey: ["channels-full"], queryFn: () => api("/channels") });
  const pubs = useQuery<Publication[]>({ queryKey: ["publications", channel], queryFn: () => api(`/publications/calendar${channel ? `?channel_id=${channel}` : ""}`) });
  const approved = useQuery<Project[]>({ queryKey: ["publications", "approved"], queryFn: () => api("/publications/approved-videos") });
  const titles = useMemo(() => new Map((approved.data ?? []).map((p) => [p.id, p.code])), [approved.data]);
  const titleOf = (id: string) => titles.get(id) ?? id.slice(0, 8);
  const chOf = (id?: string) => channels.data?.find((c) => c.id === id);
  const prepared = useMemo(() => new Set((pubs.data ?? []).filter((x) => x.status !== "CANCELLED").map((x) => x.project_id)), [pubs.data]);
  const auto = useAction((pid: string) => api<Publication[]>(`/publications/auto-prepare/${pid}`, { method: "POST" }),
    { success: (r) => (r.length ? `Đã chuẩn bị ${r.length} bài đăng` : "Mọi nền tảng đã có bài đăng"), invalidate: [["publications"]] });
  return (
    <RequirePermission perm="publish.view">
      <PageHeader code="M10" title="Publishing & Analytics" description="Lịch nội dung, bài đăng, xuất file đăng thủ công, số liệu hiệu quả sau đăng."
        actions={<NativeSelect className="w-60" value={channel} onChange={(e) => setChannel(e.target.value)} data-testid="pub-channel">
          <option value="">Mọi kênh</option>{(channels.data ?? []).map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
        </NativeSelect>} />
      <div className="mb-4 flex items-start gap-2 rounded-lg border border-slate-200 bg-white p-3 text-xs text-slate-600" data-testid="pub-api-note">
        <Info className="mt-0.5 h-4 w-4 shrink-0 text-brand-600" />
        <p><b>Tự động:</b> video được phê duyệt ở M07 → hệ thống tự soạn caption + hashtag, xếp lịch theo khung giờ của kênh (1 bài/ngày/nền tảng) và xuất gói đăng. Kênh đã gắn Fanpage (M13) → video lên Facebook dưới dạng <b>bản nháp chờ duyệt</b>, chỉ công khai khi anh/chị bấm đăng trong Meta Business Suite; trạng thái tự đồng bộ mỗi 10 phút. Nền tảng khác: <b>Xuất file</b> và <b>Đánh dấu đã đăng</b>. Dữ liệu DEMO không bao giờ được gửi lên nền tảng.</p>
      </div>
      <Tabs defaultValue="calendar">
        <TabsList>
          <TabsTrigger value="calendar">Lịch nội dung</TabsTrigger>
          <TabsTrigger value="approved" data-testid="tab-approved">Video đã duyệt</TabsTrigger>
          <TabsTrigger value="posts" data-testid="tab-posts">Bài đăng</TabsTrigger>
          <TabsTrigger value="analytics" data-testid="tab-analytics">Analytics</TabsTrigger>
        </TabsList>
        <TabsContent value="calendar"><Card><CardContent className="pt-5"><QueryView q={pubs}>{(d) => <PublishCalendar items={d.filter((p) => p.status !== "CANCELLED")} titleOf={titleOf} />}</QueryView></CardContent></Card></TabsContent>
        <TabsContent value="approved">
          <Card><CardHeader><CardTitle>Video đã duyệt — sẵn sàng phát hành</CardTitle></CardHeader>
            <CardContent>
              <QueryView q={approved} isEmpty={(d) => d.filter((p) => !channel || p.channel_id === channel).length === 0} empty={<EmptyState title="Chưa có video đã duyệt" description="Video cần đạt QC ≥ 98 và được phê duyệt tại M07." />}>
                {(d) => (
                  <Table data-testid="approved-table">
                    <THead><TR><TH>Mã</TH><TH>Tiêu đề</TH><TH>Kênh</TH><TH>Trạng thái</TH><TH>Duyệt lúc</TH><TH></TH></TR></THead>
                    <TBody>{d.filter((p) => !channel || p.channel_id === channel).map((p) => (
                      <TR key={p.id} data-testid="approved-row">
                        <TD className="font-mono text-xs"><Link className="text-brand-600 hover:underline" href={`/projects/${p.id}`}>{p.code}</Link>{p.data_mode === "DEMO" && <Badge className="ml-1" variant="yellow">DEMO</Badge>}</TD>
                        <TD className="max-w-xs truncate">{p.title}</TD><TD>{p.channel.name}</TD>
                        <TD><StatusBadge map={PROJECT_STATUS} value={p.status} /></TD><TD className="text-xs">{formatDate(p.approved_at)}</TD>
                        <TD><Can perm="publish.manage"><div className="flex flex-wrap gap-1">
                          {!prepared.has(p.id) && <Button size="sm" variant="success" loading={auto.isPending && auto.variables === p.id} onClick={() => auto.mutate(p.id)} data-testid="pub-auto"><Wand2 />Tự chuẩn bị đăng</Button>}
                          <Button size="sm" variant={prepared.has(p.id) ? "default" : "outline"} onClick={() => setCreating(p)} data-testid="pub-schedule"><CalendarPlus />Lên lịch đăng</Button>
                        </div></Can></TD>
                      </TR>))}
                    </TBody>
                  </Table>
                )}
              </QueryView>
            </CardContent></Card>
        </TabsContent>
        <TabsContent value="posts">
          <Card><CardHeader><CardTitle>Bài đăng</CardTitle></CardHeader>
            <CardContent>
              <QueryView q={pubs} isEmpty={(d) => d.length === 0} empty={<EmptyState title="Chưa có bài đăng" />}>
                {(d) => (
                  <Table data-testid="pubs-table">
                    <THead><TR><TH>Video</TH><TH>Nền tảng</TH><TH>Caption</TH><TH>Lịch</TH><TH>Trạng thái</TH><TH>URL</TH><TH></TH></TR></THead>
                    <TBody>{d.map((p) => (
                      <TR key={p.id} data-testid="pub-row" data-pub-id={p.id}>
                        <TD className="font-mono text-xs">{titleOf(p.project_id)}{p.data_mode === "DEMO" && <Badge className="ml-1" variant="yellow">DEMO</Badge>}</TD>
                        <TD>{PLATFORM_LABEL[p.platform] ?? p.platform}</TD>
                        <TD className="max-w-xs"><p className="truncate">{p.caption}</p><p className="truncate text-xs text-brand-600">{p.hashtags.join(" ")}</p></TD>
                        <TD className="text-xs">{formatDate(p.published_at ?? p.scheduled_at)}</TD>
                        <TD><StatusBadge map={PUB_STATUS} value={p.status} />{p.error_message && <p className="text-xs text-red-700">{p.error_message}</p>}</TD>
                        <TD className="max-w-[160px] truncate text-xs">{p.post_url ?? "—"}</TD>
                        <TD><PubRowActions pub={p} onChange={() => pubs.refetch()} /></TD>
                      </TR>))}
                    </TBody>
                  </Table>
                )}
              </QueryView>
            </CardContent></Card>
        </TabsContent>
        <TabsContent value="analytics"><AnalyticsPanel channelId={channel} /></TabsContent>
      </Tabs>
      <CreatePublication project={creating} channel={chOf(creating?.channel_id)} open={!!creating} onOpenChange={(o) => !o && setCreating(null)} />
    </RequirePermission>
  );
}
