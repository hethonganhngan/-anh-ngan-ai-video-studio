"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useAction } from "@/hooks/use-mutate";
import { Field } from "@/components/app/field";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { Input, NativeSelect, Textarea } from "@/components/ui/input";
import { SEVERITY } from "@/lib/labels";
import type { Project } from "@/types/api";
import { PLATFORM_LABEL, type ChannelFull } from "./types";

type Finding = { rule: string; severity: string; match: string; message: string };

export function CreatePublication({ project, channel, open, onOpenChange }: { project: Project | null; channel?: ChannelFull; open: boolean; onOpenChange: (o: boolean) => void }) {
  const platforms = channel?.platforms?.length ? channel.platforms : Object.keys(PLATFORM_LABEL);
  const [platform, setPlatform] = useState(platforms[0]);
  const [caption, setCaption] = useState("");
  const [tags, setTags] = useState("");
  const [when, setWhen] = useState("");
  const [findings, setFindings] = useState<Finding[]>([]);
  useEffect(() => { if (open) { setPlatform(platforms[0]); setCaption(project?.title ?? ""); setTags("anhngan"); setWhen(""); setFindings([]); } }, [open]); // eslint-disable-line react-hooks/exhaustive-deps
  const hashtags = tags.split(/[,\s]+/).map((t) => t.trim()).filter(Boolean);
  useEffect(() => {
    if (!open || !project) return;
    const t = setTimeout(() => {
      api<{ findings: Finding[] }>("/publications/check-caption", { body: { channel_id: project.channel_id, caption, hashtags } })
        .then((r) => setFindings(r.findings)).catch(() => undefined);
    }, 400);
    return () => clearTimeout(t);
  }, [caption, tags, open, project]); // eslint-disable-line react-hooks/exhaustive-deps
  const create = useAction((body: unknown) => api("/publications", { body }), { success: "Đã tạo lịch đăng", invalidate: [["publications"]], onSuccess: () => onOpenChange(false) });
  const blocking = findings.filter((f) => ["CRITICAL", "MAJOR"].includes(f.severity));
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent wide>
        <DialogHeader>
          <DialogTitle>Lên lịch đăng — {project?.code}</DialogTitle>
          <DialogDescription>{project?.title}</DialogDescription>
        </DialogHeader>
        <div className="grid gap-3 md:grid-cols-2">
          <Field label="Nền tảng (theo kênh)"><NativeSelect value={platform} onChange={(e) => setPlatform(e.target.value)} data-testid="pub-platform">{platforms.map((p) => <option key={p} value={p}>{PLATFORM_LABEL[p] ?? p}</option>)}</NativeSelect></Field>
          <Field label="Ngày giờ đăng (để trống = nháp)"><Input type="datetime-local" value={when} onChange={(e) => setWhen(e.target.value)} data-testid="pub-when" /></Field>
          <Field label="Caption" className="space-y-1 md:col-span-2"><Textarea rows={4} value={caption} onChange={(e) => setCaption(e.target.value)} data-testid="pub-caption" /></Field>
          <Field label="Hashtag (cách nhau bởi dấu phẩy/khoảng trắng)" className="space-y-1 md:col-span-2"><Input value={tags} onChange={(e) => setTags(e.target.value)} data-testid="pub-tags" /></Field>
        </div>
        <div className="mt-2 space-y-1" data-testid="caption-check">
          {findings.length === 0 ? <p className="text-xs text-emerald-700">✓ Caption qua bộ lọc tuân thủ</p> :
            findings.map((f, i) => <p key={i} className="text-xs"><Badge variant={SEVERITY[f.severity] ?? "gray"}>{f.severity}</Badge> {f.message}</p>)}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>Huỷ</Button>
          <Button loading={create.isPending} disabled={!project || blocking.length > 0} data-testid="pub-create-submit"
            onClick={() => create.mutate({ project_id: project!.id, platform, caption, hashtags, scheduled_at: when ? new Date(when).toISOString() : null, publish_mode: "MANUAL" })}>
            Tạo bài đăng
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
