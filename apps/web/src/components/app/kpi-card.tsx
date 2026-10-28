"use client";
import { Info } from "lucide-react";
import { useState } from "react";
import { Card } from "@/components/ui/card";
import { formatNumber, formatVND } from "@/lib/utils";
import type { Kpi } from "@/types/api";

export function KpiCard({ kpi }: { kpi: Kpi }) {
  const [show, setShow] = useState(false);
  const value = kpi.value === null || kpi.value === undefined ? "—"
    : kpi.unit === "VND" ? formatVND(kpi.value)
    : `${formatNumber(kpi.value, 1)}${kpi.unit && kpi.unit !== "VND" ? ` ${kpi.unit}` : ""}`;
  return (
    <Card className="p-4" data-testid={`kpi-${kpi.key}`}>
      <div className="flex items-start justify-between gap-2">
        <p className="text-xs font-medium uppercase tracking-wide text-slate-500">{kpi.label}</p>
        <button onClick={() => setShow((s) => !s)} className="text-slate-400 hover:text-brand-600" aria-label={`Công thức ${kpi.label}`}>
          <Info className="h-4 w-4" />
        </button>
      </div>
      <p className="mt-2 text-2xl font-bold text-slate-900" data-testid="kpi-value">{value}</p>
      {kpi.note && <p className="mt-1 text-[11px] text-amber-700">{kpi.note}</p>}
      {show && (
        <div className="mt-2 rounded-md bg-slate-50 p-2 text-[11px] text-slate-600" data-testid="kpi-formula">
          <p><b>Công thức:</b> {kpi.formula}</p>
          <p><b>Nguồn:</b> {kpi.source}</p>
        </div>
      )}
    </Card>
  );
}
