"use client";
import { useState } from "react";
import { Lightbulb } from "lucide-react";
import { toast } from "sonner";
import { api, errorMessage } from "@/lib/api";
import { useUsers } from "@/hooks/use-lookups";
import { Field } from "@/components/app/field";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Input, NativeSelect, Textarea } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { CATEGORY_LABEL, EVIDENCE_LABEL, type FeedbackDetail } from "./types";
import { EvidenceEditor, cleanEv, emptyEv, type Ev } from "./evidence-editor";

type Done = (d: FeedbackDetail) => void;

function useCall(onDone: Done) {
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const run = async (path: string, body: unknown, ok: string) => {
    setBusy(true); setErr(null);
    try { const d = await api<FeedbackDetail>(path, { body }); toast.success(ok); onDone(d); return d; }
    catch (e) { const m = errorMessage(e); setErr(m); toast.error(m); return null; }
    finally { setBusy(false); }
  };
  return { busy, err, run };
}

const ErrBox = ({ err }: { err: string | null }) => err ? <p className="rounded-lg bg-red-50 p-2 text-sm text-red-700" role="alert" data-testid="fb-action-error">{err}</p> : null;
const toIso = (d: string) => (d ? new Date(`${d}T17:00:00+07:00`).toISOString() : null);

export function ValidateForm({ id, onDone }: { id: string; onDone: Done }) {
  const [cls, setCls] = useState("FACT");
  const [ev, setEv] = useState<Ev[]>([emptyEv()]);
  const [note, setNote] = useState("");
  const { busy, err, run } = useCall(onDone);
  return (
    <Card data-testid="fb-validate">
      <CardHeader><CardTitle>Bước 2 — Xác thực (VALIDATE)</CardTitle><CardDescription>Phân loại FACT / HYPOTHESIS / UNKNOWN. Bắt buộc có ít nhất 1 bằng chứng.</CardDescription></CardHeader>
      <CardContent className="space-y-3">
        <NativeSelect value={cls} onChange={(e) => setCls(e.target.value)} data-testid="fb-validate-class">
          {Object.entries(EVIDENCE_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </NativeSelect>
        <EvidenceEditor value={ev} onChange={setEv} testid="fb-validate-ev" />
        <Input placeholder="Ghi chú" value={note} onChange={(e) => setNote(e.target.value)} />
        <ErrBox err={err} />
        <Button loading={busy} onClick={() => run(`/feedback/${id}/validate`, { evidence_class: cls, evidence: cleanEv(ev), note }, "Đã xác thực hồ sơ")} data-testid="fb-validate-submit">Xác thực</Button>
      </CardContent>
    </Card>
  );
}

export function TriageForm({ id, onDone }: { id: string; onDone: Done }) {
  const users = useUsers();
  const [f, setF] = useState({ priority: "P2", owner_id: "", deadline: "", kpi_name: "", kpi_before: "", kpi_target: "", note: "" });
  const { busy, err, run } = useCall(onDone);
  const num = (v: string) => (v === "" ? null : Number(v));
  return (
    <Card data-testid="fb-triage">
      <CardHeader><CardTitle>Bước 3 — Phân loại (TRIAGE)</CardTitle><CardDescription>Mức ưu tiên P0–P3, người phụ trách, hạn xử lý (mặc định theo ưu tiên) và KPI cần cải thiện.</CardDescription></CardHeader>
      <CardContent className="grid gap-3 md:grid-cols-3">
        <Field label="Ưu tiên"><NativeSelect value={f.priority} onChange={(e) => setF({ ...f, priority: e.target.value })} data-testid="fb-priority">
          <option value="P0">P0 — khẩn cấp (1 ngày)</option><option value="P1">P1 — cao (3 ngày)</option><option value="P2">P2 — trung bình (7 ngày)</option><option value="P3">P3 — thấp (14 ngày)</option>
        </NativeSelect></Field>
        <Field label="Người phụ trách"><NativeSelect value={f.owner_id} onChange={(e) => setF({ ...f, owner_id: e.target.value })} data-testid="fb-owner">
          <option value="">— Chọn —</option>{(users.data ?? []).map((u) => <option key={u.id} value={u.id}>{u.full_name}</option>)}
        </NativeSelect></Field>
        <Field label="Deadline (tuỳ chọn)"><Input type="date" value={f.deadline} onChange={(e) => setF({ ...f, deadline: e.target.value })} /></Field>
        <Field label="Tên KPI"><Input value={f.kpi_name} onChange={(e) => setF({ ...f, kpi_name: e.target.value })} placeholder="VD: Tỷ lệ cảnh phải tạo lại (%)" data-testid="fb-kpi-name" /></Field>
        <Field label="KPI trước"><Input type="number" value={f.kpi_before} onChange={(e) => setF({ ...f, kpi_before: e.target.value })} data-testid="fb-kpi-before" /></Field>
        <Field label="KPI mục tiêu"><Input type="number" value={f.kpi_target} onChange={(e) => setF({ ...f, kpi_target: e.target.value })} data-testid="fb-kpi-target" /></Field>
        <div className="md:col-span-3 space-y-2">
          <ErrBox err={err} />
          <Button loading={busy} disabled={!f.owner_id} data-testid="fb-triage-submit" onClick={() => run(`/feedback/${id}/triage`, {
            priority: f.priority, owner_id: f.owner_id, deadline: toIso(f.deadline), kpi_name: f.kpi_name || null,
            kpi_before: num(f.kpi_before), kpi_target: num(f.kpi_target), note: f.note,
          }, "Đã phân loại & giao người phụ trách")}>Phân loại</Button>
        </div>
      </CardContent>
    </Card>
  );
}

export function RcaForm({ id, onDone }: { id: string; onDone: Done }) {
  const [whys, setWhys] = useState(Array.from({ length: 5 }, (_, i) => ({ question: `Tại sao ${i + 1}?`, answer: "" })));
  const [rc, setRc] = useState("");
  const [cat, setCat] = useState("PROMPT");
  const [cls, setCls] = useState("HYPOTHESIS");
  const [conf, setConf] = useState("50");
  const [suggested, setSuggested] = useState(false);
  const { busy, err, run } = useCall(onDone);
  const suggest = async () => {
    try {
      const r = await api<{ whys: { question: string; answer: string }[]; root_cause: string }>(`/feedback/${id}/rca/suggest`, { method: "POST" });
      setWhys(Array.from({ length: 5 }, (_, i) => r.whys[i] ?? { question: `Tại sao ${i + 1}?`, answer: "" }));
      setRc(r.root_cause); setCls("HYPOTHESIS"); setConf("40"); setSuggested(true);
      toast.info("A08 đã gợi ý 5 Whys — đây là GIẢ THUYẾT, cần xác nhận bằng bằng chứng");
    } catch (e) { toast.error(errorMessage(e)); }
  };
  return (
    <Card data-testid="fb-rca">
      <CardHeader className="flex-row items-start justify-between">
        <div><CardTitle>Bước 4 — Nguyên nhân gốc (5 Whys)</CardTitle><CardDescription>Tối thiểu 3 câu trả lời. FACT yêu cầu mức chắc chắn ≥ 70%.</CardDescription></div>
        <Button variant="outline" size="sm" onClick={suggest} data-testid="fb-rca-suggest"><Lightbulb />Gợi ý A08</Button>
      </CardHeader>
      <CardContent className="space-y-2">
        {suggested && <Badge variant="yellow" data-testid="fb-rca-hypothesis">HYPOTHESIS — gợi ý của A08, chưa phải kết luận</Badge>}
        {whys.map((w, i) => (
          <div key={i} className="grid gap-2 md:grid-cols-12">
            <Input className="md:col-span-3" value={w.question} onChange={(e) => setWhys(whys.map((x, j) => j === i ? { ...x, question: e.target.value } : x))} />
            <Input className="md:col-span-9" placeholder="Trả lời" value={w.answer} onChange={(e) => setWhys(whys.map((x, j) => j === i ? { ...x, answer: e.target.value } : x))} data-testid={`fb-why-${i}`} />
          </div>
        ))}
        <div className="grid gap-2 md:grid-cols-4">
          <Field label="Nguyên nhân gốc" className="space-y-1 md:col-span-4"><Textarea value={rc} onChange={(e) => setRc(e.target.value)} data-testid="fb-root-cause" /></Field>
          <Field label="Nhóm nguyên nhân"><NativeSelect value={cat} onChange={(e) => setCat(e.target.value)} data-testid="fb-cause-cat">{Object.entries(CATEGORY_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</NativeSelect></Field>
          <Field label="Phân loại"><NativeSelect value={cls} onChange={(e) => setCls(e.target.value)} data-testid="fb-rca-class">{Object.entries(EVIDENCE_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</NativeSelect></Field>
          <Field label="Mức chắc chắn (%)"><Input type="number" min={0} max={100} value={conf} onChange={(e) => setConf(e.target.value)} data-testid="fb-confidence" /></Field>
        </div>
        <ErrBox err={err} />
        <Button loading={busy} data-testid="fb-rca-submit" onClick={() => run(`/feedback/${id}/rca`, {
          whys: whys.filter((w) => w.answer.trim()), root_cause: rc, cause_category: cat, evidence_class: cls, confidence_pct: Number(conf) || 0,
        }, "Đã ghi nguyên nhân gốc")}>Lưu nguyên nhân gốc</Button>
      </CardContent>
    </Card>
  );
}

export function CapaForm({ id, onDone }: { id: string; onDone: Done }) {
  const users = useUsers();
  const [f, setF] = useState({ action_type: "CORRECTIVE", description: "", owner_id: "", deadline: "" });
  const { busy, err, run } = useCall(onDone);
  return (
    <Card data-testid="fb-capa-form">
      <CardHeader><CardTitle>Thêm hành động CAPA</CardTitle><CardDescription>Cần ít nhất 1 hành động khắc phục (CORRECTIVE); khuyến khích thêm phòng ngừa (PREVENTIVE).</CardDescription></CardHeader>
      <CardContent className="grid gap-2 md:grid-cols-12">
        <NativeSelect className="md:col-span-2" value={f.action_type} onChange={(e) => setF({ ...f, action_type: e.target.value })} data-testid="fb-capa-type">
          <option value="CORRECTIVE">Khắc phục</option><option value="PREVENTIVE">Phòng ngừa</option>
        </NativeSelect>
        <Input className="md:col-span-5" placeholder="Mô tả hành động" value={f.description} onChange={(e) => setF({ ...f, description: e.target.value })} data-testid="fb-capa-desc" />
        <NativeSelect className="md:col-span-3" value={f.owner_id} onChange={(e) => setF({ ...f, owner_id: e.target.value })}>
          <option value="">Owner = người phụ trách hồ sơ</option>{(users.data ?? []).map((u) => <option key={u.id} value={u.id}>{u.full_name}</option>)}
        </NativeSelect>
        <Input className="md:col-span-2" type="date" value={f.deadline} onChange={(e) => setF({ ...f, deadline: e.target.value })} />
        <div className="md:col-span-12 space-y-2">
          <ErrBox err={err} />
          <Button size="sm" loading={busy} disabled={f.description.trim().length < 3} data-testid="fb-capa-add" onClick={async () => {
            const d = await run(`/feedback/${id}/capa`, { action_type: f.action_type, description: f.description, owner_id: f.owner_id || null, deadline: toIso(f.deadline) }, "Đã thêm CAPA");
            if (d) setF({ ...f, description: "" });
          }}>Thêm CAPA</Button>
        </div>
      </CardContent>
    </Card>
  );
}

export function SimpleAction({ path, label, ok, testid, onDone, variant }: { path: string; label: string; ok: string; testid: string; onDone: Done; variant?: "default" | "success" | "secondary" }) {
  const [note, setNote] = useState("");
  const { busy, err, run } = useCall(onDone);
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-2">
        <Input className="max-w-md" placeholder="Ghi chú (tuỳ chọn)" value={note} onChange={(e) => setNote(e.target.value)} />
        <Button variant={variant} loading={busy} onClick={() => run(path, { note }, ok)} data-testid={testid}>{label}</Button>
      </div>
      <ErrBox err={err} />
    </div>
  );
}

export function CompleteCapa({ capaId, onDone }: { capaId: string; onDone: Done }) {
  const [ev, setEv] = useState<Ev[]>([{ type: "NOTE", ref: "", note: "" }]);
  const { busy, err, run } = useCall(onDone);
  return (
    <div className="mt-2 space-y-2 rounded-lg bg-slate-50 p-2" data-testid="fb-capa-complete">
      <EvidenceEditor value={ev} onChange={setEv} testid="fb-capa-ev" />
      <ErrBox err={err} />
      <Button size="sm" variant="success" loading={busy} disabled={cleanEv(ev).length === 0} data-testid="fb-capa-done"
        onClick={() => run(`/feedback/capa/${capaId}/complete`, { evidence: cleanEv(ev) }, "Đã hoàn thành CAPA")}>Xác nhận hoàn thành</Button>
    </div>
  );
}

export function VerifyForm({ id, kpiName, onDone }: { id: string; kpiName: string | null; onDone: Done }) {
  const [method, setMethod] = useState("");
  const [kpiAfter, setKpiAfter] = useState("");
  const [passed, setPassed] = useState(true);
  const [notes, setNotes] = useState("");
  const [ev, setEv] = useState<Ev[]>([emptyEv()]);
  const { busy, err, run } = useCall(onDone);
  return (
    <Card data-testid="fb-verify">
      <CardHeader><CardTitle>Bước 7 — Kiểm chứng hiệu quả (VERIFY)</CardTitle><CardDescription>Không tuyên bố đã sửa khi chưa có kết quả kiểm thử. Không đạt → hồ sơ mở lại (REOPENED).</CardDescription></CardHeader>
      <CardContent className="space-y-3">
        <Field label="Phương pháp kiểm chứng"><Input value={method} onChange={(e) => setMethod(e.target.value)} placeholder="VD: Tạo lại 3 cảnh và so sánh nhân vật" data-testid="fb-verify-method" /></Field>
        <div className="grid gap-3 md:grid-cols-2">
          <Field label={`KPI sau${kpiName ? ` (${kpiName})` : ""}`}><Input type="number" value={kpiAfter} onChange={(e) => setKpiAfter(e.target.value)} data-testid="fb-kpi-after" /></Field>
          <div className="flex items-center gap-2 pt-6"><Switch checked={passed} onCheckedChange={setPassed} data-testid="fb-verify-passed" /><span className="text-sm">{passed ? "ĐẠT" : "KHÔNG ĐẠT"}</span></div>
        </div>
        <EvidenceEditor value={ev} onChange={setEv} testid="fb-verify-ev" />
        <Textarea placeholder="Ghi chú" value={notes} onChange={(e) => setNotes(e.target.value)} />
        <ErrBox err={err} />
        <Button loading={busy} data-testid="fb-verify-submit" onClick={() => run(`/feedback/${id}/verify`, {
          method, kpi_after: kpiAfter === "" ? null : Number(kpiAfter), passed, evidence: cleanEv(ev), notes,
        }, passed ? "Kiểm chứng ĐẠT" : "Kiểm chứng KHÔNG ĐẠT — hồ sơ mở lại")}>Ghi kết quả kiểm chứng</Button>
      </CardContent>
    </Card>
  );
}

export function RestartForm({ id, onDone }: { id: string; onDone: Done }) {
  const [target, setTarget] = useState("RCA_PENDING");
  const { busy, err, run } = useCall(onDone);
  return (
    <Card className="border-red-200" data-testid="fb-restart">
      <CardHeader><CardTitle>Hồ sơ mở lại</CardTitle><CardDescription>Kiểm chứng không đạt. Chọn quay lại phân tích nguyên nhân hoặc tiếp tục thực hiện CAPA.</CardDescription></CardHeader>
      <CardContent className="flex flex-wrap gap-2">
        <NativeSelect className="w-72" value={target} onChange={(e) => setTarget(e.target.value)} data-testid="fb-restart-target">
          <option value="RCA_PENDING">Phân tích lại nguyên nhân gốc</option><option value="IN_PROGRESS">Tiếp tục thực hiện CAPA</option>
        </NativeSelect>
        <Button loading={busy} onClick={() => run(`/feedback/${id}/restart`, { target, note: "" }, "Đã mở lại xử lý")} data-testid="fb-restart-submit">Xử lý lại</Button>
        <ErrBox err={err} />
      </CardContent>
    </Card>
  );
}

export function StandardizeForm({ id, onDone }: { id: string; onDone: Done }) {
  const [note, setNote] = useState("");
  const [lesson, setLesson] = useState(true);
  const [title, setTitle] = useState("");
  const [tpl, setTpl] = useState("A03.scene_prompt");
  const [neg, setNeg] = useState("");
  const [rule, setRule] = useState("");
  const { busy, err, run } = useCall(onDone);
  return (
    <Card data-testid="fb-standardize">
      <CardHeader><CardTitle>Bước 8 — Chuẩn hoá (STANDARDIZE)</CardTitle><CardDescription>Ghi nhận SOP/prompt/checklist được cập nhật. Có thể soạn bài học (A09) — chỉ áp dụng vào cấu hình chuẩn sau khi được duyệt ở M09.</CardDescription></CardHeader>
      <CardContent className="space-y-3">
        <Textarea placeholder="Nội dung chuẩn hoá (bắt buộc)" value={note} onChange={(e) => setNote(e.target.value)} data-testid="fb-std-note" />
        <div className="flex items-center gap-2"><Switch checked={lesson} onCheckedChange={setLesson} /><span className="text-sm">Tạo bài học (Lessons Learned)</span></div>
        {lesson && (
          <div className="grid gap-2 md:grid-cols-2">
            <Input placeholder="Tiêu đề bài học (tuỳ chọn)" value={title} onChange={(e) => setTitle(e.target.value)} />
            <NativeSelect value={tpl} onChange={(e) => setTpl(e.target.value)}>
              <option value="">Không đề xuất thay đổi prompt</option><option value="A03.scene_prompt">A03.scene_prompt — Prompt cảnh</option><option value="A02.script">A02.script — Kịch bản</option>
            </NativeSelect>
            {tpl && <Input placeholder="Thêm vào Negative Prompt" value={neg} onChange={(e) => setNeg(e.target.value)} data-testid="fb-std-neg" />}
            {tpl && <Input placeholder="Thêm quy tắc (rule)" value={rule} onChange={(e) => setRule(e.target.value)} data-testid="fb-std-rule" />}
          </div>
        )}
        <ErrBox err={err} />
        <Button loading={busy} disabled={note.trim().length < 3} data-testid="fb-std-submit" onClick={() => run(`/feedback/${id}/standardize`, {
          note, create_lesson: lesson, lesson_title: title || null,
          proposed_change: lesson && tpl && (neg || rule) ? { template_code: tpl, append_negative: neg, append_rule: rule } : null,
        }, "Đã chuẩn hoá")}>Chuẩn hoá</Button>
      </CardContent>
    </Card>
  );
}
