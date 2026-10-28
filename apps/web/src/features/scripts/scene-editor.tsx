"use client";
import { Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input, Textarea } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { Dialogue } from "@/types/api";

export type SceneDraft = {
  title: string; scene_type: string; action: string; dialogue: Dialogue[]; setting: string; camera: string;
  lighting: string; sound: string; duration_sec: number;
};

export const SCENE_KEYS: (keyof SceneDraft)[] = ["title", "scene_type", "action", "dialogue", "setting", "camera", "lighting", "sound", "duration_sec"];

export function toDraft(s: Partial<SceneDraft> & Record<string, unknown>): SceneDraft {
  return {
    title: String(s.title ?? ""), scene_type: String(s.scene_type ?? ""), action: String(s.action ?? ""),
    dialogue: Array.isArray(s.dialogue) ? (s.dialogue as Dialogue[]).map((d) => ({ speaker: d.speaker ?? "", text: d.text ?? "" })) : [],
    setting: String(s.setting ?? ""), camera: String(s.camera ?? ""), lighting: String(s.lighting ?? ""),
    sound: String(s.sound ?? ""), duration_sec: Number(s.duration_sec ?? 8),
  };
}

/** Kiểm tra phía client: 1 hành động chính, ≤ 2 câu thoại, ≤ 8 giây. */
export function validateDraft(s: SceneDraft, idx: number): string[] {
  const e: string[] = [];
  if (!s.action.trim()) e.push(`Cảnh ${idx + 1}: thiếu hành động chính`);
  if (s.dialogue.length > 2) e.push(`Cảnh ${idx + 1}: tối đa 2 câu thoại`);
  if (s.dialogue.some((d) => !d.text.trim())) e.push(`Cảnh ${idx + 1}: câu thoại trống`);
  if (s.dialogue.some((d) => d.text.length > 160)) e.push(`Cảnh ${idx + 1}: câu thoại quá 160 ký tự`);
  if (s.duration_sec > 8 || s.duration_sec < 1) e.push(`Cảnh ${idx + 1}: thời lượng 1–8 giây`);
  return e;
}

export function SceneEditor({ idx, value, onChange, onRemove }: { idx: number; value: SceneDraft; onChange: (v: SceneDraft) => void; onRemove?: () => void }) {
  const set = <K extends keyof SceneDraft>(k: K, v: SceneDraft[K]) => onChange({ ...value, [k]: v });
  return (
    <div className="space-y-2 rounded-lg border border-slate-200 p-3" data-testid={`scene-editor-${idx}`}>
      <div className="flex items-center gap-2">
        <span className="rounded bg-brand-50 px-2 py-0.5 text-xs font-semibold text-brand-700">Cảnh {idx + 1}</span>
        <Input className="flex-1" value={value.title} onChange={(e) => set("title", e.target.value)} placeholder="Tiêu đề cảnh" />
        <Input className="w-24" type="number" min={1} max={8} value={value.duration_sec} onChange={(e) => set("duration_sec", Number(e.target.value))} aria-label="Thời lượng (giây)" />
        {onRemove && <Button size="icon" variant="ghost" onClick={onRemove} aria-label="Xoá cảnh"><Trash2 /></Button>}
      </div>
      <div><Label>Hành động chính (1 hành động)</Label><Textarea rows={2} value={value.action} onChange={(e) => set("action", e.target.value)} data-testid={`scene-action-${idx}`} /></div>
      <div className="space-y-1">
        <Label>Thoại (tối đa 2 câu)</Label>
        {value.dialogue.map((d, i) => (
          <div key={i} className="flex gap-2">
            <Input className="w-40" value={d.speaker} placeholder="Người nói" onChange={(e) => set("dialogue", value.dialogue.map((x, j) => (j === i ? { ...x, speaker: e.target.value } : x)))} />
            <Input className="flex-1" value={d.text} placeholder="Câu thoại" data-testid={`scene-${idx}-line-${i}`}
              onChange={(e) => set("dialogue", value.dialogue.map((x, j) => (j === i ? { ...x, text: e.target.value } : x)))} />
            <Button size="icon" variant="ghost" aria-label="Xoá thoại" onClick={() => set("dialogue", value.dialogue.filter((_, j) => j !== i))}><Trash2 /></Button>
          </div>
        ))}
        <Button size="sm" variant="outline" onClick={() => set("dialogue", [...value.dialogue, { speaker: "", text: "" }])} data-testid={`scene-${idx}-add-line`}><Plus />Thêm thoại</Button>
      </div>
      <div className="grid gap-2 md:grid-cols-2">
        <div><Label>Bối cảnh</Label><Input value={value.setting} onChange={(e) => set("setting", e.target.value)} /></div>
        <div><Label>Loại cảnh</Label><Input value={value.scene_type} onChange={(e) => set("scene_type", e.target.value)} /></div>
        <div><Label>Máy quay</Label><Input value={value.camera} onChange={(e) => set("camera", e.target.value)} /></div>
        <div><Label>Ánh sáng</Label><Input value={value.lighting} onChange={(e) => set("lighting", e.target.value)} /></div>
        <div className="md:col-span-2"><Label>Âm thanh</Label><Input value={value.sound} onChange={(e) => set("sound", e.target.value)} /></div>
      </div>
    </div>
  );
}
