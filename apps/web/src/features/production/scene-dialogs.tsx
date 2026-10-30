"use client";
import { useState } from "react";
import { ExternalLink, FileUp, ShieldCheck, Wand2 } from "lucide-react";
import { toast } from "sonner";
import { api, ApiError, errorMessage } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input, NativeSelect, Textarea } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { FLOW_URL_DEFAULT, toFlowPrompt } from "@/features/production/flow-prompt";

type ImportResult = { asset_id: string; job_id: string; warnings: string[] };

export function FlowImportDialog({ sceneId, sceneNo, onDone }: { sceneId: string; sceneNo: number; onDone: () => void }) {
  const [open, setOpen] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [cost, setCost] = useState("0");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [errors, setErrors] = useState<string[]>([]);
  const submit = async () => {
    if (!file) { toast.error("Chọn file video tải từ Google Flow"); return; }
    setBusy(true); setErrors([]);
    const fd = new FormData();
    fd.append("file", file);
    fd.append("actual_cost", cost || "0");
    fd.append("note", note);
    try {
      const r = await api<ImportResult>(`/scenes/${sceneId}/import-flow`, { form: fd });
      toast.success(`Đã nhập cảnh ${sceneNo} từ Flow${r.warnings.length ? ` (cảnh báo: ${r.warnings.join("; ")})` : ""}`);
      setOpen(false); setFile(null); onDone();
    } catch (e) {
      const d = e instanceof ApiError ? (e.details as { errors?: string[] } | null) : null;
      setErrors(d?.errors?.length ? d.errors : [errorMessage(e)]);
    } finally { setBusy(false); }
  };
  return (
    <>
      <Button size="sm" variant="outline" onClick={() => { setErrors([]); setOpen(true); }} data-testid={`import-flow-${sceneNo - 1}`}><FileUp />Nhập từ Flow</Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Nhập cảnh {sceneNo} từ Google Flow</DialogTitle>
            <DialogDescription>Google Flow không có API công khai: tạo video trên Flow bằng prompt của cảnh, tải MP4 về rồi nhập tại đây. Yêu cầu: dọc 9:16, ≥ 720x1280, 2–30 giây.</DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <div><Label>File video</Label><Input type="file" accept="video/mp4,video/quicktime,video/webm" onChange={(e) => setFile(e.target.files?.[0] ?? null)} data-testid="flow-file" /></div>
            <div><Label>Chi phí thực tế trên Flow (VND)</Label><Input type="number" min={0} value={cost} onChange={(e) => setCost(e.target.value)} /></div>
            <div><Label>Ghi chú</Label><Input value={note} onChange={(e) => setNote(e.target.value)} placeholder="Ví dụ: tạo lần 2 trên Flow" /></div>
            {errors.length > 0 && <ul className="list-disc rounded-lg bg-red-50 p-3 pl-6 text-sm text-red-700" role="alert" data-testid="flow-errors">{errors.map((x) => <li key={x}>{x}</li>)}</ul>}
          </div>
          <DialogFooter><Button variant="outline" onClick={() => setOpen(false)}>Huỷ</Button><Button onClick={submit} loading={busy} data-testid="flow-submit">Nhập & kiểm tra</Button></DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

const FLOW_URL_KEY = "anngan.flowUrl";

/** Mở Google Flow để tạo cảnh: chép prompt dạng 1 đoạn văn vào clipboard rồi mở dự án Flow (Flow không có API nhận prompt). */
export function FlowCreateDialog({ sceneNo, promptText, durationSec }: { sceneNo: number; promptText: string; durationSec: number }) {
  const [open, setOpen] = useState(false);
  const [text, setText] = useState("");
  const [url, setUrl] = useState(FLOW_URL_DEFAULT);
  const show = () => {
    setText(toFlowPrompt(promptText, durationSec));
    try { setUrl(localStorage.getItem(FLOW_URL_KEY) || FLOW_URL_DEFAULT); } catch { /* trình duyệt chặn storage */ }
    setOpen(true);
  };
  const go = async () => {
    try { localStorage.setItem(FLOW_URL_KEY, url); } catch { /* bỏ qua */ }
    window.open(url, "google-flow");
    try { await navigator.clipboard.writeText(text); toast.success(`Đã chép prompt cảnh ${sceneNo} — dán (Ctrl+V) vào ô "Bạn muốn tạo những gì?" trên Flow`); }
    catch { toast.error("Không chép tự động được — bôi đen prompt trong hộp này rồi Ctrl+C"); }
  };
  return (
    <>
      <Button size="sm" onClick={show} disabled={!promptText.trim()} data-testid={`flow-create-${sceneNo - 1}`}><Wand2 />Tạo trên Flow</Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Tạo cảnh {sceneNo} trên Google Flow</DialogTitle>
            <DialogDescription>Bấm “Chép prompt & mở Flow” → trên Flow gắn nhân vật (Thêm vào câu lệnh), dán prompt, chọn Video · 9:16 · {durationSec} giây · x1 rồi gửi. Xong tải MP4 về và bấm “Nhập từ Flow”.</DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <div><Label>Prompt cho Flow (sửa được trước khi chép)</Label><Textarea rows={9} value={text} onChange={(e) => setText(e.target.value)} data-testid="flow-prompt" /></div>
            <div><Label>Link dự án Flow (lưu lại cho lần sau)</Label><Input value={url} onChange={(e) => setUrl(e.target.value)} placeholder={FLOW_URL_DEFAULT} data-testid="flow-url" /></div>
            <p className="text-xs text-slate-500">Kiểm tra trước khi tải: đúng mặt & trang phục nhân vật, thoại tiếng Việt rõ, logo/chữ không méo, không cận cảnh bao bì sữa cho trẻ dưới 24 tháng hay thương hiệu đối thủ.</p>
          </div>
          <DialogFooter><Button variant="outline" onClick={() => setOpen(false)}>Đóng</Button><Button onClick={go} disabled={!/^https:\/\//.test(url)} data-testid="flow-open"><ExternalLink />Chép prompt & mở Flow</Button></DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

const CRITERIA: [string, string][] =[["character", "Nhân vật"], ["setting", "Bối cảnh"], ["visual", "Hình ảnh"], ["voice", "Giọng nói"], ["lipsync", "Khẩu hình"], ["audio", "Âm thanh"], ["script", "Kịch bản"], ["brand", "Thương hiệu"], ["compliance", "Tuân thủ"], ["hook", "Hook"]];

export function SceneQCDialog({ sceneId, sceneNo, onDone }: { sceneId: string; sceneNo: number; onDone: () => void }) {
  const [open, setOpen] = useState(false);
  const [passed, setPassed] = useState(true);
  const [notes, setNotes] = useState("");
  const [criterion, setCriterion] = useState("character");
  const [severity, setSeverity] = useState("MAJOR");
  const [busy, setBusy] = useState(false);
  const submit = async () => {
    if (!passed && notes.trim().length < 3) { toast.error("Mô tả lỗi khi đánh giá không đạt"); return; }
    setBusy(true);
    try {
      await api(`/scenes/${sceneId}/qc`, { body: { passed, notes, criterion, severity: passed ? null : severity } });
      toast.success(`Đã ghi nhận QC cảnh ${sceneNo}: ${passed ? "ĐẠT" : "KHÔNG ĐẠT"}`);
      setOpen(false); setNotes(""); onDone();
    } catch (e) { toast.error(errorMessage(e)); } finally { setBusy(false); }
  };
  return (
    <>
      <Button size="sm" variant="ghost" onClick={() => setOpen(true)} data-testid={`scene-qc-${sceneNo - 1}`}><ShieldCheck />QC cảnh</Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader><DialogTitle>QC thủ công cảnh {sceneNo}</DialogTitle><DialogDescription>Nhân vật, khẩu hình, giọng nói cần người xem trực tiếp.</DialogDescription></DialogHeader>
          <div className="space-y-3">
            <div className="flex gap-4 text-sm">
              <label className="flex items-center gap-1"><input type="radio" checked={passed} onChange={() => setPassed(true)} data-testid="qc-pass" />Đạt</label>
              <label className="flex items-center gap-1"><input type="radio" checked={!passed} onChange={() => setPassed(false)} data-testid="qc-fail" />Không đạt</label>
            </div>
            {!passed && (
              <div className="grid grid-cols-2 gap-2">
                <div><Label>Tiêu chí</Label><NativeSelect value={criterion} onChange={(e) => setCriterion(e.target.value)}>{CRITERIA.map(([k, l]) => <option key={k} value={k}>{l}</option>)}</NativeSelect></div>
                <div><Label>Mức độ</Label><NativeSelect value={severity} onChange={(e) => setSeverity(e.target.value)}><option value="CRITICAL">CRITICAL</option><option value="MAJOR">MAJOR</option><option value="MINOR">MINOR</option></NativeSelect></div>
              </div>
            )}
            <div><Label>Nhận xét</Label><Textarea value={notes} onChange={(e) => setNotes(e.target.value)} data-testid="qc-notes" /></div>
          </div>
          <DialogFooter><Button variant="outline" onClick={() => setOpen(false)}>Huỷ</Button><Button onClick={submit} loading={busy} data-testid="qc-submit">Lưu đánh giá</Button></DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
