"use client";
import { useRouter, useSearchParams, usePathname } from "next/navigation";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { api } from "@/lib/api";
import { useAction } from "@/hooks/use-mutate";
import { useChannels } from "@/hooks/use-lookups";
import { PageHeader } from "@/components/app/page-header";
import { RequirePermission, Can } from "@/components/app/require";
import { EmptyState, QueryView } from "@/components/app/states";
import { StatusBadge } from "@/components/app/status-badge";
import { Field } from "@/components/app/field";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input, NativeSelect, Textarea } from "@/components/ui/input";
import { LESSON_STATUS, LESSON_TYPES } from "@/lib/labels";
import { cn, formatDate } from "@/lib/utils";
import { LessonDetail } from "@/features/lessons/lesson-detail";
import { CATEGORY_LABEL } from "@/features/feedback/types";
import type { Character, Lesson, Page } from "@/types/api";

function CreateLesson({ open, onOpenChange, onCreated }: { open: boolean; onOpenChange: (o: boolean) => void; onCreated: (l: Lesson) => void }) {
  const channels = useChannels();
  const [f, setF] = useState({ lesson_type: "EFFECTIVE_PROMPT", title: "", lesson: "", root_cause: "", channel_id: "", error_category: "", provider_code: "", prompt_example: "", tags: "", template_code: "", append_negative: "", append_rule: "" });
  const create = useAction((body: unknown) => api<Lesson>("/lessons", { body }), { success: (l) => `Đã tạo ${l.code}`, invalidate: [["lessons"]], onSuccess: (l) => { onOpenChange(false); onCreated(l); } });
  const s = (k: keyof typeof f) => (e: { target: { value: string } }) => setF({ ...f, [k]: e.target.value });
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent wide>
        <DialogHeader><DialogTitle>Tạo bài học thủ công</DialogTitle></DialogHeader>
        <div className="grid gap-3 md:grid-cols-2">
          <Field label="Loại bài học"><NativeSelect value={f.lesson_type} onChange={s("lesson_type")} data-testid="ll-type">{Object.entries(LESSON_TYPES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</NativeSelect></Field>
          <Field label="Kênh"><NativeSelect value={f.channel_id} onChange={s("channel_id")}><option value="">Mọi kênh</option>{(channels.data ?? []).map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</NativeSelect></Field>
          <Field label="Tiêu đề" className="space-y-1 md:col-span-2"><Input value={f.title} onChange={s("title")} data-testid="ll-title" /></Field>
          <Field label="Nội dung bài học" className="space-y-1 md:col-span-2"><Textarea value={f.lesson} onChange={s("lesson")} data-testid="ll-lesson" /></Field>
          <Field label="Nguyên nhân gốc"><Input value={f.root_cause} onChange={s("root_cause")} /></Field>
          <Field label="Loại lỗi"><NativeSelect value={f.error_category} onChange={s("error_category")}><option value="">—</option>{Object.entries(CATEGORY_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</NativeSelect></Field>
          <Field label="Nhà cung cấp"><Input value={f.provider_code} onChange={s("provider_code")} placeholder="mock, manual_flow…" /></Field>
          <Field label="Tag (phẩy)"><Input value={f.tags} onChange={s("tags")} /></Field>
          <Field label="Prompt ví dụ" className="space-y-1 md:col-span-2"><Textarea value={f.prompt_example} onChange={s("prompt_example")} /></Field>
          <Field label="Đề xuất áp dụng vào template"><NativeSelect value={f.template_code} onChange={s("template_code")} data-testid="ll-template"><option value="">Không</option><option value="A03.scene_prompt">A03.scene_prompt</option><option value="A02.script">A02.script</option></NativeSelect></Field>
          <Field label="Thêm Negative Prompt"><Input value={f.append_negative} onChange={s("append_negative")} disabled={!f.template_code} data-testid="ll-neg" /></Field>
          <Field label="Thêm quy tắc" className="space-y-1 md:col-span-2"><Input value={f.append_rule} onChange={s("append_rule")} disabled={!f.template_code} data-testid="ll-rule" /></Field>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>Huỷ</Button>
          <Button loading={create.isPending} disabled={f.title.trim().length < 3 || f.lesson.trim().length < 3} data-testid="ll-create-submit" onClick={() => create.mutate({
            lesson_type: f.lesson_type, title: f.title, lesson: f.lesson, root_cause: f.root_cause, channel_id: f.channel_id || null,
            error_category: f.error_category || null, provider_code: f.provider_code || null, prompt_example: f.prompt_example,
            tags: f.tags.split(",").map((t) => t.trim()).filter(Boolean),
            proposed_change: f.template_code ? { template_code: f.template_code, append_negative: f.append_negative, append_rule: f.append_rule } : null,
          })}>Tạo bài học</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export default function LessonsPage() {
  const sp = useSearchParams();
  const router = useRouter();
  const path = usePathname();
  const selected = sp.get("id");
  const select = (id: string) => router.replace(`${path}?id=${id}`);
  const channels = useChannels();
  const chars = useQuery<Character[]>({ queryKey: ["characters-mini"], queryFn: () => api("/characters"), retry: false });
  const [f, setF] = useState({ q: "", channel_id: "", character_id: "", error_category: "", provider_code: "", lesson_type: "", status: "" });
  const [open, setOpen] = useState(false);
  const p = new URLSearchParams({ page_size: "200" });
  Object.entries(f).forEach(([k, v]) => v && p.set(k, v));
  const list = useQuery<Page<Lesson>>({ queryKey: ["lessons", p.toString()], queryFn: () => api(`/lessons?${p}`) });
  const s = (k: keyof typeof f) => (e: { target: { value: string } }) => setF({ ...f, [k]: e.target.value });
  return (
    <RequirePermission perm="lesson.view">
      <PageHeader code="M09" title="AI Lessons Learned" description="Kho bài học đã kiểm chứng: lỗi đã xử lý, prompt hiệu quả/thất bại, Lock tốt, CAPA hiệu quả. Chỉ áp dụng vào cấu hình chuẩn sau khi được duyệt; có rollback."
        actions={<Can perm="lesson.create"><Button onClick={() => setOpen(true)} data-testid="ll-new"><Plus />Tạo bài học</Button></Can>} />
      <Card className="mb-4">
        <CardContent className="grid gap-2 pt-5 md:grid-cols-7">
          <Input className="md:col-span-2" placeholder="Từ khoá…" value={f.q} onChange={s("q")} data-testid="ll-filter-q" />
          <NativeSelect value={f.channel_id} onChange={s("channel_id")}><option value="">Mọi kênh</option>{(channels.data ?? []).map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</NativeSelect>
          <NativeSelect value={f.character_id} onChange={s("character_id")}><option value="">Mọi nhân vật</option>{(chars.data ?? []).map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</NativeSelect>
          <NativeSelect value={f.error_category} onChange={s("error_category")}><option value="">Mọi loại lỗi</option>{Object.entries(CATEGORY_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</NativeSelect>
          <Input placeholder="Nhà cung cấp" value={f.provider_code} onChange={s("provider_code")} />
          <NativeSelect value={f.status} onChange={s("status")} data-testid="ll-filter-status"><option value="">Mọi trạng thái</option>{Object.entries(LESSON_STATUS).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}</NativeSelect>
          <NativeSelect className="md:col-span-2" value={f.lesson_type} onChange={s("lesson_type")}><option value="">Mọi loại bài học</option>{Object.entries(LESSON_TYPES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</NativeSelect>
        </CardContent>
      </Card>
      <div className="grid gap-4 lg:grid-cols-5">
        <div className="lg:col-span-2">
          <QueryView q={list} isEmpty={(d) => d.items.length === 0} empty={<EmptyState title="Chưa có bài học" description="Bài học được soạn từ hồ sơ Feedback đã kiểm chứng hoặc tạo thủ công." />}>
            {(d) => (
              <div className="space-y-2" data-testid="ll-list">
                {d.items.map((l) => (
                  <button key={l.id} onClick={() => select(l.id)} data-testid="ll-row"
                    className={cn("w-full rounded-xl border bg-white p-3 text-left shadow-sm hover:ring-2 hover:ring-brand-500", selected === l.id ? "border-brand-500" : "border-slate-200")}>
                    <div className="flex items-center justify-between gap-2"><span className="font-mono text-xs text-slate-500">{l.code}</span><StatusBadge map={LESSON_STATUS} value={l.status} /></div>
                    <p className="mt-1 line-clamp-2 font-medium">{l.title}</p>
                    <div className="mt-1 flex flex-wrap gap-1"><Badge variant="gray">{LESSON_TYPES[l.lesson_type] ?? l.lesson_type}</Badge>{l.tags.slice(0, 3).map((t) => <Badge key={t} variant="gray">#{t}</Badge>)}</div>
                    <p className="mt-1 text-[11px] text-slate-400">{formatDate(l.created_at)}</p>
                  </button>
                ))}
              </div>
            )}
          </QueryView>
        </div>
        <div className="lg:col-span-3">{selected ? <LessonDetail id={selected} /> : <EmptyState title="Chọn một bài học để xem chi tiết" />}</div>
      </div>
      <CreateLesson open={open} onOpenChange={setOpen} onCreated={(l) => select(l.id)} />
    </RequirePermission>
  );
}
