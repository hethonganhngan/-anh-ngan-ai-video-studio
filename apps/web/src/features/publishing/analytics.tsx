"use client";
import { useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, Lightbulb, Upload } from "lucide-react";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { toast } from "sonner";
import { api, apiBase, errorMessage } from "@/lib/api";
import { Can } from "@/components/app/require";
import { EmptyState, QueryView } from "@/components/app/states";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { formatDate, formatNumber, formatVND } from "@/lib/utils";
import { PLATFORM_LABEL, type Insights, type PerfRow } from "./types";

export function AnalyticsPanel({ channelId }: { channelId: string }) {
  const qc = useQueryClient();
  const qs = channelId ? `?channel_id=${channelId}` : "";
  const perf = useQuery<PerfRow[]>({ queryKey: ["performance", channelId], queryFn: () => api(`/analytics/performance${qs}`) });
  const [insights, setInsights] = useState<Insights | null>(null);
  const [loadingIns, setLoadingIns] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const [importRes, setImportRes] = useState<{ imported: number; errors: { row: number; error: string }[] } | null>(null);
  const runInsights = async () => {
    setLoadingIns(true);
    try { setInsights(await api<Insights>(`/analytics/insights${qs}`)); } catch (e) { toast.error(errorMessage(e)); } finally { setLoadingIns(false); }
  };
  const importCsv = async () => {
    const f = fileRef.current?.files?.[0];
    if (!f) { toast.error("Chọn file CSV"); return; }
    const fd = new FormData(); fd.append("file", f);
    try {
      const r = await api<{ imported: number; errors: { row: number; error: string }[] }>("/analytics/import", { form: fd });
      setImportRes(r); toast.success(`Đã nhập ${r.imported} dòng`); qc.invalidateQueries({ queryKey: ["performance"] });
    } catch (e) { toast.error(errorMessage(e)); }
  };
  return (
    <div className="space-y-4">
      <Card>
        <CardHeader className="flex-row flex-wrap items-center justify-between gap-2">
          <div><CardTitle>Hiệu quả video sau đăng</CardTitle><CardDescription>Tương tác = (thích + bình luận + chia sẻ + lưu) / lượt xem. Chi phí lấy từ cost_records của dự án.</CardDescription></div>
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" onClick={runInsights} loading={loadingIns} data-testid="run-insights"><Lightbulb />A10 Insights</Button>
            <Button variant="outline" asChild><a href={`${apiBase()}/api/v1/analytics/export.csv${qs}`} data-testid="export-csv"><Download />Xuất CSV</a></Button>
          </div>
        </CardHeader>
        <CardContent>
          {insights && (
            <div className="mb-4 rounded-lg bg-brand-50 p-3 text-sm" data-testid="insights">
              <p className="font-semibold">A10 AI Analytics (phép tính xác định)</p>
              <ul className="ml-4 list-disc">{insights.insights.map((x, i) => <li key={i}>{x}</li>)}</ul>
              {insights.anomalies.length > 0 && <div className="mt-2"><p className="font-semibold text-orange-700">Bất thường</p><ul className="ml-4 list-disc">{insights.anomalies.map((a) => <li key={a.publication_id}>{a.project_code}: {a.reason}</li>)}</ul></div>}
            </div>
          )}
          <QueryView q={perf} isEmpty={(d) => d.length === 0} empty={<EmptyState title="Chưa có bài đã đăng" description="Đánh dấu bài đã đăng rồi nhập số liệu để xem hiệu quả." />}>
            {(rows) => (<>
              <div className="mb-4 h-64" data-testid="perf-chart">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={rows.filter((r) => r.has_data).slice(0, 12).map((r) => ({ name: r.project_code, views: r.views, engagement: r.engagement_rate ?? 0 }))}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="name" fontSize={11} />
                    <YAxis yAxisId="l" fontSize={11} />
                    <YAxis yAxisId="r" orientation="right" fontSize={11} unit="%" />
                    <Tooltip />
                    <Legend />
                    <Bar yAxisId="l" dataKey="views" name="Lượt xem" fill="#2563eb" />
                    <Bar yAxisId="r" dataKey="engagement" name="Tương tác (%)" fill="#10b981" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
              <Table data-testid="perf-table">
                <THead><TR><TH>Video</TH><TH>Nền tảng</TH><TH>Đăng lúc</TH><TH>Xem</TH><TH>Thích</TH><TH>BL</TH><TH>Chia sẻ</TH><TH>Giữ chân</TH><TH>Chuyển đổi</TH><TH>Tương tác</TH><TH>Chi phí</TH><TH>Chi phí/1000 view</TH></TR></THead>
                <TBody>
                  {rows.map((r) => (
                    <TR key={r.publication_id} data-testid="perf-row">
                      <TD><p className="font-mono text-xs">{r.project_code}</p><p className="max-w-[200px] truncate text-xs text-slate-500">{r.title}</p>{r.data_mode === "DEMO" && <Badge variant="yellow">DEMO</Badge>}</TD>
                      <TD>{PLATFORM_LABEL[r.platform] ?? r.platform}</TD>
                      <TD className="text-xs">{formatDate(r.published_at)}</TD>
                      <TD>{r.has_data ? formatNumber(r.views) : <span className="text-xs text-slate-400">chưa nhập</span>}</TD>
                      <TD>{formatNumber(r.likes)}</TD><TD>{formatNumber(r.comments)}</TD><TD>{formatNumber(r.shares)}</TD>
                      <TD>{r.retention_rate != null ? `${r.retention_rate}%` : "—"}</TD>
                      <TD>{r.conversions ?? "—"}</TD>
                      <TD data-testid="perf-engagement">{r.engagement_rate != null ? `${r.engagement_rate}%` : "—"}</TD>
                      <TD>{formatVND(r.cost)}</TD>
                      <TD>{r.cost_per_1k_views != null ? formatVND(r.cost_per_1k_views) : "—"}</TD>
                    </TR>
                  ))}
                </TBody>
              </Table>
            </>)}
          </QueryView>
        </CardContent>
      </Card>
      <Can perm="analytics.enter">
        <Card>
          <CardHeader><CardTitle>Nhập số liệu từ CSV</CardTitle>
            <CardDescription>Cột: post_url hoặc publication_id, captured_at (ISO), views, likes, comments, shares, saves, retention_rate, avg_watch_sec, conversions. Dùng khi chưa kết nối API nền tảng.</CardDescription></CardHeader>
          <CardContent className="space-y-2">
            <div className="flex flex-wrap gap-2"><Input ref={fileRef} type="file" accept=".csv,text/csv" className="max-w-sm" data-testid="csv-file" /><Button onClick={importCsv} data-testid="csv-import"><Upload />Nhập CSV</Button></div>
            {importRes && <div className="text-sm" data-testid="csv-result">Đã nhập {importRes.imported} dòng.{importRes.errors.map((e) => <p key={e.row} className="text-red-700">Dòng {e.row}: {e.error}</p>)}</div>}
          </CardContent>
        </Card>
      </Can>
    </div>
  );
}
