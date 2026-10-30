"use client";
import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useForm, useWatch } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { Calculator, Clapperboard } from "lucide-react";
import { api, errorMessage } from "@/lib/api";
import { useChannels, useUsers } from "@/hooks/use-lookups";
import { PageHeader } from "@/components/app/page-header";
import { RequirePermission } from "@/components/app/require";
import { Field } from "@/components/app/field";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, NativeSelect, Textarea } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { AUTOMATION } from "@/lib/labels";
import { formatVND } from "@/lib/utils";
import type { Character, SceneLock, Voice } from "@/types/api";

const schema = z.object({
  channel_id: z.string().min(1, "Chọn kênh"),
  title: z.string().max(255).optional(),
  topic: z.string().trim().min(5, "Chủ đề tối thiểu 5 ký tự").max(2000),
  objective: z.string().max(2000).optional(),
  target_audience: z.string().max(2000).optional(),
  duration_sec: z.number({ message: "Nhập số giây" }).int().min(8, "Tối thiểu 8 giây").max(120, "Tối đa 120 giây"),
  quantity: z.number({ message: "Nhập số lượng" }).int().min(1, "Tối thiểu 1").max(20, "Tối đa 20 video/lô"),
  style: z.string().max(160).optional(),
  character_ids: z.array(z.string()).max(6, "Tối đa 6 nhân vật"),
  scene_lock_ids: z.array(z.string()).max(6),
  setting: z.string().max(255).optional(),
  voice_profile_id: z.string().optional(),
  cta: z.string().max(255).optional(),
  budget_limit: z.number({ message: "Nhập ngân sách (0 = không giới hạn)" }).min(0, "Không âm"),
  automation_level: z.enum(["MANUAL", "ASSISTED", "AUTO"]),
  video_provider_code: z.string().min(1, "Chọn nhà cung cấp"),
  owner_id: z.string().optional(),
  deadline: z.string().optional(),
  priority: z.enum(["LOW", "NORMAL", "HIGH", "URGENT"]),
  run_director: z.boolean(),
});
type F = z.infer<typeof schema>;

type Provider = { code: string; name: string; kind: string; is_real: boolean; available: boolean; connection_status: string; unit_cost_vnd_per_sec: number };
type Estimate = { scene_count: number; scene_seconds: number; duration_sec: number; provider: string; provider_kind: string; simulated: boolean; cost_per_scene: number; cost_per_video: number; cost_per_video_with_retry_buffer: number; total_estimate: number; within_budget: boolean };
type CreateRes = { projects: { id: string; code: string }[]; batch_id: string | null; duplicate: boolean; estimate: Estimate; warnings: string[] };

export default function CreatePage() {
  const router = useRouter();
  const channels = useChannels();
  const users = useUsers();
  const characters = useQuery<Character[]>({ queryKey: ["characters"], queryFn: () => api("/characters") });
  const voices = useQuery<Voice[]>({ queryKey: ["voices"], queryFn: () => api("/voices") });
  const sceneLocks = useQuery<SceneLock[]>({ queryKey: ["scene-locks"], queryFn: () => api("/scene-locks") });
  const providers = useQuery<Provider[]>({ queryKey: ["video-providers"], queryFn: () => api("/video-providers") });
  const [idemKey, setIdemKey] = useState<string>("");
  const [warnings, setWarnings] = useState<string[]>([]);
  const [submitted, setSubmitted] = useState(false);
  useEffect(() => { setIdemKey(crypto.randomUUID()); }, []);

  const { register, handleSubmit, control, setValue, formState: { errors, isSubmitting } } = useForm<F>({
    resolver: zodResolver(schema),
    defaultValues: {
      channel_id: "", topic: "", duration_sec: 32, quantity: 1, character_ids: [], scene_lock_ids: [], budget_limit: 0,
      automation_level: "AUTO", video_provider_code: "", priority: "NORMAL", run_director: true,
    },
  });
  const autofilled = useRef({ voice: false, characters: false });
  const w = useWatch({ control });
  useEffect(() => {
    if (!w.channel_id && channels.data?.length) setValue("channel_id", channels.data[0].id);
  }, [channels.data, w.channel_id, setValue]);
  const availableProviders = (providers.data ?? []).filter((p) => p.available);
  useEffect(() => {
    // Mặc định "nhập chủ đề là chạy": ưu tiên provider API thật đã sẵn sàng (tạo tự động), không thì provider khả dụng đầu tiên
    if (providers.data && !availableProviders.some((p) => p.code === w.video_provider_code)) {
      // nhiều provider thật → chọn rẻ nhất (vd. Flow tự động dùng lượt gói Google, 0đ)
      const real = availableProviders.filter((p) => p.is_real).sort((a, b) => a.unit_cost_vnd_per_sec - b.unit_cost_vnd_per_sec);
      const pick = real[0] ?? availableProviders[0];
      if (pick) setValue("video_provider_code", pick.code);
    }
  }, [providers.data, availableProviders, w.video_provider_code, setValue]);
  useEffect(() => {
    // Giọng AI đã consent (TTS tự đọc được) và nhân vật đã khoá (có ảnh tham chiếu) — người dùng vẫn đổi được
    // Ưu tiên giọng đã gắn cho nhân vật (giọng chính chủ), rồi giọng đã khoá
    const c = (characters.data ?? []).find((x) => x.status === "LOCKED" && x.active_lock_id);
    const usable = (x: Voice) => x.provider_code !== "manual" && x.consent_status === "GRANTED";
    const all = voices.data ?? [];
    const v = all.find((x) => x.id === c?.voice_profile_id && usable(x)) ?? all.find((x) => usable(x) && x.status === "LOCKED") ?? all.find(usable);
    if (v && !w.voice_profile_id && !autofilled.current.voice) { autofilled.current.voice = true; setValue("voice_profile_id", v.id); }
    if (c && !(w.character_ids ?? []).length && !autofilled.current.characters) { autofilled.current.characters = true; setValue("character_ids", [c.id]); }
  }, [voices.data, characters.data, w.voice_profile_id, w.character_ids, setValue]);

  const estKey = useMemo(() => [w.duration_sec, w.quantity, w.video_provider_code, w.budget_limit], [w.duration_sec, w.quantity, w.video_provider_code, w.budget_limit]);
  const estimate = useQuery<Estimate>({
    queryKey: ["estimate", ...estKey],
    enabled: !!w.video_provider_code && Number(w.duration_sec) >= 8 && Number(w.quantity) >= 1,
    queryFn: () => api("/projects/estimate", { body: { duration_sec: Number(w.duration_sec), quantity: Number(w.quantity), video_provider_code: w.video_provider_code, budget_limit: Number(w.budget_limit) || 0 } }),
  });

  const toggle = (field: "character_ids" | "scene_lock_ids", id: string) => {
    const cur = (w[field] ?? []) as string[];
    setValue(field, cur.includes(id) ? cur.filter((x) => x !== id) : [...cur, id], { shouldValidate: true });
  };

  const onSubmit = async (v: F) => {
    if (submitted) return;
    setWarnings([]);
    const body: Record<string, unknown> = {
      channel_id: v.channel_id, topic: v.topic, objective: v.objective ?? "", target_audience: v.target_audience ?? "",
      duration_sec: v.duration_sec, quantity: v.quantity, style: v.style ?? "", character_ids: v.character_ids,
      scene_lock_ids: v.scene_lock_ids, setting: v.setting ?? "", cta: v.cta ?? "", budget_limit: v.budget_limit,
      automation_level: v.automation_level, video_provider_code: v.video_provider_code, priority: v.priority,
      idempotency_key: idemKey,
    };
    if (v.title) body.title = v.title;
    if (v.voice_profile_id) body.voice_profile_id = v.voice_profile_id;
    if (v.owner_id) body.owner_id = v.owner_id;
    if (v.deadline) body.deadline = `${v.deadline}T17:00:00+07:00`;
    try {
      const res = await api<CreateRes>("/projects", { body });
      setSubmitted(true); // giữ nguyên mã chống trùng & khoá form cho tới khi rời trang
      if (res.warnings?.length) setWarnings(res.warnings);
      toast.success(res.duplicate ? "Yêu cầu đã được tạo trước đó — không tạo trùng" : `Đã tạo ${res.projects.length} video`);
      if (v.run_director && !res.duplicate) {
        for (const p of res.projects) {
          try { await api(`/projects/${p.id}/advance`, { method: "POST" }); } catch (e) { toast.error(`${p.code}: ${errorMessage(e)}`); }
        }
      }
      router.push(res.projects.length === 1 ? `/projects/${res.projects[0].id}` : "/projects");
    } catch (e) {
      toast.error(errorMessage(e));
    }
  };

  const est = estimate.data;
  return (
    <RequirePermission perm="project.create">
      <PageHeader code="M02" title="Trung tâm tạo video" description="Nhập brief để tạo một video hoặc một lô video. Hệ thống kiểm tra dữ liệu và chống tạo trùng." />
      <form onSubmit={handleSubmit(onSubmit)} className="grid gap-4 lg:grid-cols-3" noValidate data-testid="create-form">
        <div className="space-y-4 lg:col-span-2">
          <Card>
            <CardHeader><CardTitle>Nội dung</CardTitle></CardHeader>
            <CardContent className="grid gap-3 md:grid-cols-2">
              <Field label="Kênh *" error={errors.channel_id?.message}>
                <NativeSelect {...register("channel_id")} data-testid="f-channel">
                  <option value="">— Chọn kênh —</option>
                  {(channels.data ?? []).map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
                </NativeSelect>
              </Field>
              <Field label="Tiêu đề (tuỳ chọn)" error={errors.title?.message}><Input {...register("title")} data-testid="f-title" /></Field>
              <Field label="Chủ đề *" error={errors.topic?.message} className="space-y-1 md:col-span-2">
                <Textarea {...register("topic")} placeholder="VD: Cách chọn sữa phù hợp cho bé trên 2 tuổi" data-testid="f-topic" aria-invalid={!!errors.topic} />
              </Field>
              <Field label="Mục tiêu"><Textarea {...register("objective")} placeholder="Tăng niềm tin, mời đến cửa hàng tư vấn…" data-testid="f-objective" /></Field>
              <Field label="Khách hàng mục tiêu"><Textarea {...register("target_audience")} placeholder="Mẹ bỉm 25–35 tuổi…" data-testid="f-audience" /></Field>
              <Field label="Phong cách"><Input {...register("style")} placeholder="Ấm áp, đời thường" data-testid="f-style" /></Field>
              <Field label="CTA"><Input {...register("cta")} placeholder="Ghé Ánh Ngân để được tư vấn nhé" data-testid="f-cta" /></Field>
            </CardContent>
          </Card>
          <Card>
            <CardHeader><CardTitle>Nhân vật, bối cảnh, giọng nói</CardTitle></CardHeader>
            <CardContent className="grid gap-3 md:grid-cols-2">
              <Field label="Nhân vật" error={errors.character_ids?.message}>
                <div className="max-h-40 space-y-1 overflow-y-auto rounded-lg border border-slate-200 p-2" data-testid="f-characters">
                  {(characters.data ?? []).length === 0 && <p className="text-xs text-slate-500">Chưa có nhân vật (tạo tại M04)</p>}
                  {(characters.data ?? []).map((c) => (
                    <label key={c.id} className="flex items-center gap-2 text-sm">
                      <input type="checkbox" checked={(w.character_ids ?? []).includes(c.id)} onChange={() => toggle("character_ids", c.id)} />
                      {c.code} · {c.name} {c.status === "LOCKED" ? <Badge variant="green">Đã khoá</Badge> : <Badge variant="yellow">Chưa khoá</Badge>}
                    </label>
                  ))}
                </div>
              </Field>
              <Field label="Bối cảnh (Scene Lock)">
                <div className="max-h-40 space-y-1 overflow-y-auto rounded-lg border border-slate-200 p-2" data-testid="f-scenelocks">
                  {(sceneLocks.data ?? []).length === 0 && <p className="text-xs text-slate-500">Chưa có Scene Lock</p>}
                  {(sceneLocks.data ?? []).map((s) => (
                    <label key={s.id} className="flex items-center gap-2 text-sm">
                      <input type="checkbox" checked={(w.scene_lock_ids ?? []).includes(s.id)} onChange={() => toggle("scene_lock_ids", s.id)} />
                      {s.code} v{s.version_no} · {s.name} {s.status !== "APPROVED" && <Badge variant="yellow">{s.status}</Badge>}
                    </label>
                  ))}
                </div>
              </Field>
              <Field label="Mô tả bối cảnh"><Input {...register("setting")} placeholder="Cửa hàng Ánh Ngân, quầy tư vấn" data-testid="f-setting" /></Field>
              <Field label="Giọng nói">
                <NativeSelect {...register("voice_profile_id")} data-testid="f-voice">
                  <option value="">— Không chọn —</option>
                  {(voices.data ?? []).map((v) => <option key={v.id} value={v.id}>{v.code} · {v.name} ({v.accent}){v.consent_status !== "GRANTED" ? " — chưa consent" : ""}</option>)}
                </NativeSelect>
              </Field>
            </CardContent>
          </Card>
          <Card>
            <CardHeader><CardTitle>Sản xuất & quản lý</CardTitle></CardHeader>
            <CardContent className="grid gap-3 md:grid-cols-3">
              <Field label="Thời lượng (giây) *" error={errors.duration_sec?.message} hint="Mỗi cảnh 8 giây, video dọc 9:16">
                <Input type="number" {...register("duration_sec", { valueAsNumber: true })} data-testid="f-duration" />
              </Field>
              <Field label="Số lượng (lô) *" error={errors.quantity?.message}>
                <Input type="number" {...register("quantity", { valueAsNumber: true })} data-testid="f-quantity" />
              </Field>
              <Field label="Ngân sách / video (VND)" error={errors.budget_limit?.message} hint="0 = theo hạn mức chung">
                <Input type="number" step="1000" {...register("budget_limit", { valueAsNumber: true })} data-testid="f-budget" />
              </Field>
              <Field label="Mức tự động hoá">
                <NativeSelect {...register("automation_level")} data-testid="f-automation">
                  {Object.entries(AUTOMATION).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                </NativeSelect>
              </Field>
              <Field label="Nhà cung cấp video *" error={errors.video_provider_code?.message}>
                <NativeSelect {...register("video_provider_code")} data-testid="f-provider">
                  {(providers.data ?? []).map((p) => (
                    <option key={p.code} value={p.code} disabled={!p.available}>{p.name}{!p.available ? " — chưa khả dụng" : ""}</option>
                  ))}
                </NativeSelect>
              </Field>
              <Field label="Ưu tiên">
                <NativeSelect {...register("priority")} data-testid="f-priority">
                  <option value="LOW">Thấp</option><option value="NORMAL">Bình thường</option><option value="HIGH">Cao</option><option value="URGENT">Khẩn</option>
                </NativeSelect>
              </Field>
              <Field label="Người phụ trách">
                <NativeSelect {...register("owner_id")} data-testid="f-owner">
                  <option value="">— Tôi —</option>
                  {(users.data ?? []).map((u) => <option key={u.id} value={u.id}>{u.full_name}</option>)}
                </NativeSelect>
              </Field>
              <Field label="Deadline"><Input type="date" {...register("deadline")} data-testid="f-deadline" /></Field>
              <label className="flex items-center gap-2 self-end pb-2 text-sm">
                <input type="checkbox" {...register("run_director")} data-testid="f-run-director" /> Tạo & chạy AI Director
              </label>
            </CardContent>
          </Card>
        </div>
        <div className="space-y-4">
          <Card className="lg:sticky lg:top-20">
            <CardHeader><CardTitle className="flex items-center gap-2"><Calculator className="h-4 w-4" />Ước tính chi phí</CardTitle></CardHeader>
            <CardContent className="space-y-2 text-sm" data-testid="estimate">
              {estimate.isLoading && <p className="text-slate-500">Đang tính…</p>}
              {estimate.error && <p className="text-red-600">{errorMessage(estimate.error)}</p>}
              {est && (
                <>
                  <div className="flex justify-between"><span>Số cảnh / video</span><b data-testid="est-scenes">{est.scene_count} × {est.scene_seconds}s</b></div>
                  <div className="flex justify-between"><span>Chi phí / cảnh</span><b>{formatVND(est.cost_per_scene)}</b></div>
                  <div className="flex justify-between"><span>Chi phí / video</span><b data-testid="est-video">{formatVND(est.cost_per_video)}</b></div>
                  <div className="flex justify-between"><span>Dự phòng retry (+30%)</span><b>{formatVND(est.cost_per_video_with_retry_buffer)}</b></div>
                  <div className="flex justify-between border-t pt-2"><span>Tổng ({w.quantity} video)</span><b data-testid="est-total">{formatVND(est.total_estimate)}</b></div>
                  {est.simulated && <Badge variant="yellow">Chi phí mô phỏng — {est.provider}</Badge>}
                  {!est.within_budget && <p className="rounded bg-red-50 p-2 text-red-700" data-testid="est-over">Vượt ngân sách dự án — tác vụ tạo cảnh sẽ bị chặn.</p>}
                </>
              )}
            </CardContent>
          </Card>
          {warnings.length > 0 && (
            <Card className="border-amber-200" data-testid="create-warnings">
              <CardContent className="space-y-1 pt-5 text-sm text-amber-800">{warnings.map((x, i) => <p key={i}>⚠ {x}</p>)}</CardContent>
            </Card>
          )}
          <Button type="submit" size="lg" className="w-full" loading={isSubmitting} disabled={!idemKey || submitted} data-testid="create-submit">
            <Clapperboard />{Number(w.quantity) > 1 ? `Tạo lô ${w.quantity} video` : "Tạo video"}
          </Button>
          <p className="text-xs text-slate-500">Mã chống trùng: <code data-testid="idem-key">{idemKey.slice(0, 8)}</code></p>
        </div>
      </form>
    </RequirePermission>
  );
}
