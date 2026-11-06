"use client";
import Link from "next/link";
import { ChevronRight, Info } from "lucide-react";
import { useState } from "react";
import { Card } from "@/components/ui/card";
import { formatNumber, formatVND } from "@/lib/utils";
import type { Kpi } from "@/types/api";

/** Thẻ KPI. Có `href` thì cả thẻ bấm được để mở màn hình xử lý (nút (i) vẫn bấm riêng). */
export function KpiCard({ kpi, href, action }: { kpi: Kpi; href?: string; action?: string }) {
  const [show, setShow] = useState(false);
  const value = kpi.value === null || kpi.value === undefined ? "—"
    : kpi.unit === "VND" ? formatVND(kpi.value)
    : `${formatNumber(kpi.value, 1)}${kpi.unit && kpi.unit !== "VND" ? ` ${kpi.unit}` : ""}`;
  return (
    <Card className={`relative p-4 ${href ? "transition hover:shadow-md hover:ring-2 hover:ring-brand-500" : ""}`} data-testid={`kpi-${kpi.key}`}>
      {href && <Link href={href} className="absolute inset-0 rounded-[inherit]" aria-label={`${kpi.label}: ${action ?? "Xem chi tiết"}`} data-testid="kpi-link" />}
      <div className="flex items-start justify-between gap-2">
        <p className="text-xs font-medium uppercase tracking-wide text-slate-500">{kpi.label}</p>
        <button onClick={() => setShow((s) => !s)} className="relative z-10 text-slate-400 hover:text-brand-600" aria-label={`Công thức ${kpi.label}`}>
          <Info className="h-4 w-4" />
        </button>
      </div>
      <p className="mt-2 text-2xl font-bold text-slate-900" data-testid="kpi-value">{value}</p>
      {kpi.note && <p className="mt-1 text-[11px] text-amber-700">{kpi.note}</p>}
      {href && <p className="mt-1 flex items-center text-[11px] font-medium text-brand-600">{action ?? "Xem chi tiết"}<ChevronRight className="h-3 w-3" /></p>}
      {show && (
        <div className="relative z-10 mt-2 rounded-md bg-slate-50 p-2 text-[11px] text-slate-600" data-testid="kpi-formula">
          <p><b>Công thức:</b> {kpi.formula}</p>
          <p><b>Nguồn:</b> {kpi.source}</p>
        </div>
      )}
    </Card>
  );
}
