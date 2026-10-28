"use client";
import { useMemo, useState } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { PUB_STATUS } from "@/lib/labels";
import { cn } from "@/lib/utils";
import type { Publication } from "@/types/api";
import { PLATFORM_LABEL } from "./types";

const WD = ["T2", "T3", "T4", "T5", "T6", "T7", "CN"];
const key = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
const startOfWeek = (d: Date) => { const x = new Date(d); const wd = (x.getDay() + 6) % 7; x.setDate(x.getDate() - wd); x.setHours(0, 0, 0, 0); return x; };

export function PublishCalendar({ items, titleOf }: { items: Publication[]; titleOf: (projectId: string) => string }) {
  const [mode, setMode] = useState<"month" | "week">("month");
  const [anchor, setAnchor] = useState(() => new Date());
  const days = useMemo(() => {
    if (mode === "week") { const s = startOfWeek(anchor); return Array.from({ length: 7 }, (_, i) => { const d = new Date(s); d.setDate(s.getDate() + i); return d; }); }
    const first = new Date(anchor.getFullYear(), anchor.getMonth(), 1);
    const s = startOfWeek(first);
    return Array.from({ length: 42 }, (_, i) => { const d = new Date(s); d.setDate(s.getDate() + i); return d; });
  }, [mode, anchor]);
  const byDay = useMemo(() => {
    const m = new Map<string, Publication[]>();
    items.forEach((p) => { const t = p.published_at ?? p.scheduled_at; if (!t) return; const k = key(new Date(t)); m.set(k, [...(m.get(k) ?? []), p]); });
    return m;
  }, [items]);
  const shift = (n: number) => { const d = new Date(anchor); if (mode === "week") d.setDate(d.getDate() + 7 * n); else d.setMonth(d.getMonth() + n); setAnchor(d); };
  const unscheduled = items.filter((p) => !p.scheduled_at && !p.published_at);
  return (
    <div className="space-y-3" data-testid="pub-calendar">
      <div className="flex flex-wrap items-center gap-2">
        <Button size="icon" variant="outline" onClick={() => shift(-1)} aria-label="Trước"><ChevronLeft /></Button>
        <Button size="icon" variant="outline" onClick={() => shift(1)} aria-label="Sau"><ChevronRight /></Button>
        <Button size="sm" variant="ghost" onClick={() => setAnchor(new Date())}>Hôm nay</Button>
        <p className="font-semibold" data-testid="cal-label">{mode === "month" ? `Tháng ${anchor.getMonth() + 1}/${anchor.getFullYear()}` : `Tuần từ ${startOfWeek(anchor).toLocaleDateString("vi-VN")}`}</p>
        <div className="ml-auto flex gap-1">
          <Button size="sm" variant={mode === "month" ? "default" : "outline"} onClick={() => setMode("month")}>Tháng</Button>
          <Button size="sm" variant={mode === "week" ? "default" : "outline"} onClick={() => setMode("week")} data-testid="cal-week">Tuần</Button>
        </div>
      </div>
      <div className="grid grid-cols-7 gap-1 text-center text-xs font-semibold text-slate-500">{WD.map((w) => <div key={w}>{w}</div>)}</div>
      <div className="grid grid-cols-7 gap-1">
        {days.map((d) => {
          const list = byDay.get(key(d)) ?? [];
          const out = mode === "month" && d.getMonth() !== anchor.getMonth();
          return (
            <div key={key(d)} className={cn("min-h-24 rounded-lg border border-slate-200 bg-white p-1 text-left", out && "bg-slate-50 opacity-60", key(d) === key(new Date()) && "border-brand-500")} data-testid="cal-day" data-date={key(d)}>
              <p className="text-[11px] text-slate-500">{d.getDate()}</p>
              {list.map((p) => (
                <div key={p.id} className="mt-1 rounded bg-brand-50 p-1 text-[11px]" data-testid="cal-item" title={p.caption}>
                  <p className="truncate font-medium">{PLATFORM_LABEL[p.platform] ?? p.platform} · {titleOf(p.project_id)}</p>
                  <Badge variant={PUB_STATUS[p.status]?.variant ?? "gray"}>{PUB_STATUS[p.status]?.label ?? p.status}</Badge>
                </div>
              ))}
            </div>
          );
        })}
      </div>
      {unscheduled.length > 0 && <p className="text-xs text-slate-500">{unscheduled.length} bài chưa đặt ngày đăng.</p>}
    </div>
  );
}
