"use client";
import { useEffect, useMemo, useState } from "react";
import { Plus, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { api, ApiError, errorMessage } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input, NativeSelect, Textarea } from "@/components/ui/input";
import type { QCView } from "./types";

const METHOD_LABEL: Record<string, { label: string; v: "green" | "default" | "orange" }> = {
  AUTO: { label: "Tự động đo", v: "green" }, ASSISTED: { label: "Máy gợi ý · người xác nhận", v: "default" }, MANUAL: { label: "Chỉ người chấm", v: "orange" },
};

type NewFinding = { criterion: string; severity: string; description: string };

export function ScoreForm({ view, onDone }: { view: QCView; onDone: () => void }) {
  const agent = view.agent_final;
  const init = useMemo(() => Object.fromEntries(view.criteria.map((c) => {
    const s = agent?.scores?.[c.key]?.score;
    return [c.key, { score: s === null || s === undefined ? "" : String(s), note: "" }];
  })), [view.criteria, agent]);
  const [scores, setScores] = useState<Record<string, { score: string; note: string }>>(init);
  const [notes, setNotes] = useState("");
  const [findings, setFindings] = useState<NewFinding[]>([]);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => setScores(init), [init]);

  const total = view.criteria.reduce((s, c) => s + (Number(scores[c.key]?.score) || 0), 0);
  const allFilled = view.criteria.every((c) => scores[c.key]?.score !== "");
  const min = view.policy.min_total;

  const submit = async () => {
    setErr(null);
    for (const c of view.criteria) {
      const v = Number(scores[c.key].score);
      if (scores[c.key].score === "" || isNaN(v) || v < 0 || v > 10) { setErr(`Điểm "${c.label}" phải từ 0–10`); return; }
      const auto = agent?.scores?.[c.key]?.score;
      if (c.method === "AUTO" && auto !== null && auto !== undefined && v > auto) {
        setErr(`${c.label} là tiêu chí đo tự động: không được chấm cao hơn kết quả đo (${auto}) [QC_AUTO_OVERRIDE]`); return;
      }
    }
    setBusy(true);
    try {
      const body = {
        scores: Object.fromEntries(view.criteria.map((c) => [c.key, { score: Number(scores[c.key].score), note: scores[c.key].note }])),
        notes, findings: findings.filter((f) => f.description.trim().length >= 3),
      };
      const r = await api<{ result: string; total_score: number }>(`/projects/${view.project.id}/qc/final`, { body });
      if (r.result === "PASS") toast.success(`QC ĐẠT ${r.total_score}/100 — chuyển chờ phê duyệt`);
      else toast.warning(`QC KHÔNG ĐẠT (${r.total_score}/100)`);
      setFindings([]);
      onDone();
    } catch (e) {
      const msg = errorMessage(e);
      setErr(e instanceof ApiError && e.code === "QC_AUTO_OVERRIDE" ? `${msg} [QC_AUTO_OVERRIDE]` : msg);
    } finally { setBusy(false); }
  };

  return (
    <Card data-testid="qc-score-form">
      <CardHeader>
        <CardTitle>Chấm QC tổng thể — 10 tiêu chí × 10 điểm</CardTitle>
        <CardDescription>Điểm gợi ý từ A07 đã điền sẵn. Tiêu chí AUTO không được chấm cao hơn kết quả đo. Tiêu chí MANUAL bắt buộc người xem video.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="divide-y divide-slate-100 rounded-lg border border-slate-200">
          {view.criteria.map((c) => {
            const auto = agent?.scores?.[c.key];
            return (
              <div key={c.key} className="grid gap-2 p-3 md:grid-cols-12 md:items-center" data-testid={`criterion-${c.key}`}>
                <div className="md:col-span-5">
                  <p className="font-medium">{c.label} <Badge variant={METHOD_LABEL[c.method].v}>{METHOD_LABEL[c.method].label}</Badge></p>
                  <p className="text-xs text-slate-500">{c.desc}</p>
                  {auto && auto.score !== null && <p className="text-xs text-slate-600">A07 gợi ý: <b>{auto.score}</b>{c.method === "AUTO" && " (trần điểm)"}</p>}
                  {view.agent_final?.pending_manual.includes(c.key) && c.method === "MANUAL" && <p className="text-xs text-orange-700">Chờ đánh giá thủ công</p>}
                </div>
                <Input className="md:col-span-2" type="number" min={0} max={10} step={1} value={scores[c.key]?.score ?? ""}
                  onChange={(e) => setScores({ ...scores, [c.key]: { ...scores[c.key], score: e.target.value } })} data-testid={`score-${c.key}`} aria-label={`Điểm ${c.label}`} />
                <Input className="md:col-span-5" placeholder="Ghi chú" value={scores[c.key]?.note ?? ""}
                  onChange={(e) => setScores({ ...scores, [c.key]: { ...scores[c.key], note: e.target.value } })} />
              </div>
            );
          })}
        </div>
        <div className="flex flex-wrap items-center gap-3 rounded-lg bg-slate-50 p-3">
          <p className="text-lg font-bold" data-testid="qc-total">Tổng: {total}/100</p>
          <Badge variant={allFilled && total >= min ? "green" : "red"}>{allFilled && total >= min ? `Đạt ngưỡng ${min}` : `Chưa đạt ngưỡng ${min}`}</Badge>
        </div>
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <p className="text-sm font-medium">Lỗi phát hiện thêm</p>
            <Button size="sm" variant="outline" onClick={() => setFindings([...findings, { criterion: "character", severity: "MAJOR", description: "" }])} data-testid="add-finding"><Plus />Thêm lỗi</Button>
          </div>
          {findings.map((f, i) => (
            <div key={i} className="grid gap-2 md:grid-cols-12" data-testid="new-finding">
              <NativeSelect className="md:col-span-3" value={f.criterion} onChange={(e) => setFindings(findings.map((x, j) => j === i ? { ...x, criterion: e.target.value } : x))}>
                {view.criteria.map((c) => <option key={c.key} value={c.key}>{c.label}</option>)}
              </NativeSelect>
              <NativeSelect className="md:col-span-2" value={f.severity} onChange={(e) => setFindings(findings.map((x, j) => j === i ? { ...x, severity: e.target.value } : x))} data-testid="new-finding-severity">
                <option value="CRITICAL">CRITICAL</option><option value="MAJOR">MAJOR</option><option value="MINOR">MINOR</option>
              </NativeSelect>
              <Input className="md:col-span-6" placeholder="Mô tả lỗi" value={f.description} onChange={(e) => setFindings(findings.map((x, j) => j === i ? { ...x, description: e.target.value } : x))} data-testid="new-finding-desc" />
              <Button className="md:col-span-1" size="icon" variant="ghost" onClick={() => setFindings(findings.filter((_, j) => j !== i))} aria-label="Xoá"><Trash2 /></Button>
            </div>
          ))}
        </div>
        <Textarea placeholder="Nhận xét chung" value={notes} onChange={(e) => setNotes(e.target.value)} data-testid="qc-notes" />
        {err && <p className="rounded-lg bg-red-50 p-2 text-sm text-red-700" role="alert" data-testid="qc-error">{err}</p>}
        <Button onClick={submit} loading={busy} disabled={!allFilled} data-testid="qc-submit">Gửi kết quả QC</Button>
      </CardContent>
    </Card>
  );
}
