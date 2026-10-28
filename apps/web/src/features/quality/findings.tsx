"use client";
import Link from "next/link";
import { useState } from "react";
import { CheckCircle2, LifeBuoy, ShieldOff } from "lucide-react";
import { api } from "@/lib/api";
import { useAction } from "@/hooks/use-mutate";
import { Can } from "@/components/app/require";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/input";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { SEVERITY } from "@/lib/labels";
import { formatDate } from "@/lib/utils";
import type { Criterion, Finding } from "@/types/api";

export function FindingsTable({ findings, criteria, onChange }: { findings: Finding[]; criteria: Criterion[]; onChange: () => void }) {
  const [target, setTarget] = useState<{ f: Finding; action: "RESOLVE" | "WAIVE" } | null>(null);
  const [note, setNote] = useState("");
  const resolve = useAction((v: { id: string; action: string; note: string }) => api(`/qc-findings/${v.id}/resolve`, { body: { action: v.action, note: v.note } }),
    { success: "Đã cập nhật lỗi QC", onSuccess: () => { setTarget(null); onChange(); } });
  const toFb = useAction((id: string) => api<{ feedback_case_id: string; code: string }>(`/qc-findings/${id}/feedback`, { method: "POST" }),
    { success: (r) => `Đã tạo/gắn Feedback Case ${r.code}`, onSuccess: onChange });
  const label = (k: string) => criteria.find((c) => c.key === k)?.label ?? k;
  return (
    <Card>
      <CardHeader><CardTitle>Lỗi QC ({findings.filter((f) => f.status === "OPEN").length} đang mở)</CardTitle></CardHeader>
      <CardContent>
        {findings.length === 0 ? <p className="text-sm text-slate-500">Không có lỗi QC</p> : (
          <Table data-testid="findings-table">
            <THead><TR><TH>Mức</TH><TH>Tiêu chí</TH><TH>Mô tả</TH><TH>Trạng thái</TH><TH>Thời gian</TH><TH></TH></TR></THead>
            <TBody>
              {findings.map((f) => (
                <TR key={f.id} data-testid="finding-row">
                  <TD><Badge variant={SEVERITY[f.severity] ?? "gray"}>{f.severity}</Badge></TD>
                  <TD>{label(f.criterion)}</TD>
                  <TD className="max-w-md text-sm">{f.description}{f.resolution_note && <p className="text-xs text-slate-500">Xử lý: {f.resolution_note}</p>}</TD>
                  <TD><Badge variant={f.status === "OPEN" ? "red" : f.status === "RESOLVED" ? "green" : "gray"}>{f.status === "OPEN" ? "Đang mở" : f.status === "RESOLVED" ? "Đã khắc phục" : "Đã miễn"}</Badge></TD>
                  <TD className="text-xs">{formatDate(f.created_at)}</TD>
                  <TD className="space-x-1 whitespace-nowrap text-right">
                    {f.status === "OPEN" && (
                      <Can perm="qc.waive">
                        <Button size="sm" variant="ghost" onClick={() => { setNote(""); setTarget({ f, action: "RESOLVE" }); }} data-testid="finding-resolve"><CheckCircle2 />Khắc phục</Button>
                        {f.severity !== "CRITICAL" && <Button size="sm" variant="ghost" onClick={() => { setNote(""); setTarget({ f, action: "WAIVE" }); }} data-testid="finding-waive"><ShieldOff />Miễn</Button>}
                      </Can>
                    )}
                    {f.feedback_case_id ? (
                      <Link className="text-xs text-brand-600 hover:underline" href={`/feedback/${f.feedback_case_id}`}>Xem Feedback</Link>
                    ) : (
                      <Can perm="feedback.create"><Button size="sm" variant="ghost" onClick={() => toFb.mutate(f.id)} data-testid="finding-feedback"><LifeBuoy />Tạo Feedback</Button></Can>
                    )}
                  </TD>
                </TR>
              ))}
            </TBody>
          </Table>
        )}
        <p className="mt-2 text-xs text-slate-500">Lỗi CRITICAL không được miễn — bắt buộc khắc phục.</p>
      </CardContent>
      <Dialog open={!!target} onOpenChange={(o) => !o && setTarget(null)}>
        <DialogContent>
          <DialogHeader><DialogTitle>{target?.action === "WAIVE" ? "Miễn lỗi QC" : "Xác nhận đã khắc phục"}</DialogTitle></DialogHeader>
          <p className="text-sm text-slate-600">{target?.f.description}</p>
          <Textarea placeholder="Ghi chú / bằng chứng xử lý (bắt buộc)" value={note} onChange={(e) => setNote(e.target.value)} data-testid="finding-note" />
          <DialogFooter>
            <Button variant="outline" onClick={() => setTarget(null)}>Huỷ</Button>
            <Button disabled={note.trim().length < 3} loading={resolve.isPending} data-testid="finding-confirm"
              onClick={() => target && resolve.mutate({ id: target.f.id, action: target.action, note })}>Lưu</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Card>
  );
}
