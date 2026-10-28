"use client";
import { Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input, NativeSelect } from "@/components/ui/input";

export type Ev = { type: string; ref: string; note: string };
export const emptyEv = (): Ev => ({ type: "NOTE", ref: "", note: "" });
export const cleanEv = (list: Ev[]) => list.filter((e) => e.ref.trim() || e.note.trim());

export function EvidenceEditor({ value, onChange, testid = "evidence" }: { value: Ev[]; onChange: (v: Ev[]) => void; testid?: string }) {
  return (
    <div className="space-y-2" data-testid={testid}>
      {value.map((e, i) => (
        <div key={i} className="grid gap-2 md:grid-cols-12">
          <NativeSelect className="md:col-span-3" value={e.type} onChange={(x) => onChange(value.map((v, j) => j === i ? { ...v, type: x.target.value } : v))}>
            <option value="NOTE">Ghi chú</option><option value="URL">Đường dẫn</option><option value="ASSET">Tài nguyên (ID)</option>
            <option value="QC_FINDING">Lỗi QC</option><option value="METRIC">Số liệu</option><option value="SCREENSHOT">Ảnh chụp</option>
          </NativeSelect>
          <Input className="md:col-span-3" placeholder="Tham chiếu (URL/ID)" value={e.ref} onChange={(x) => onChange(value.map((v, j) => j === i ? { ...v, ref: x.target.value } : v))} data-testid={`${testid}-ref`} />
          <Input className="md:col-span-5" placeholder="Mô tả bằng chứng" value={e.note} onChange={(x) => onChange(value.map((v, j) => j === i ? { ...v, note: x.target.value } : v))} data-testid={`${testid}-note`} />
          <Button className="md:col-span-1" size="icon" variant="ghost" onClick={() => onChange(value.filter((_, j) => j !== i))} aria-label="Xoá bằng chứng"><Trash2 /></Button>
        </div>
      ))}
      <Button size="sm" variant="outline" onClick={() => onChange([...value, emptyEv()])} data-testid={`${testid}-add`}><Plus />Thêm bằng chứng</Button>
    </div>
  );
}
