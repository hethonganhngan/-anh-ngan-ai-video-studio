"use client";
import { useQuery } from "@tanstack/react-query";
import { useRouter, useSearchParams, usePathname } from "next/navigation";
import { api } from "@/lib/api";
import { NativeSelect } from "@/components/ui/input";
import { PROJECT_STATUS } from "@/lib/labels";
import type { Page, Project } from "@/types/api";

/** Chọn dự án và đồng bộ với query ?project=. statuses: lọc trạng thái phù hợp màn hình. */
export function useProjectParam(): [string | null, (id: string | null) => void] {
  const sp = useSearchParams();
  const router = useRouter();
  const path = usePathname();
  const id = sp.get("project");
  const set = (v: string | null) => {
    const p = new URLSearchParams(sp.toString());
    if (v) p.set("project", v); else p.delete("project");
    router.replace(`${path}?${p.toString()}`);
  };
  return [id, set];
}

export function ProjectPicker({ statuses, value, onChange, className }: {
  statuses?: string[]; value: string | null; onChange: (id: string | null) => void; className?: string;
}) {
  const q = useQuery<Page<Project>>({
    queryKey: ["projects", "picker", statuses?.join(",")],
    queryFn: () => api(`/projects?page_size=200${statuses ? `&status=${statuses.join(",")}` : ""}`),
  });
  return (
    <NativeSelect className={className ?? "w-full md:w-96"} value={value ?? ""} onChange={(e) => onChange(e.target.value || null)}
      aria-label="Chọn dự án" data-testid="project-picker">
      <option value="">{q.isLoading ? "Đang tải dự án…" : "— Chọn dự án —"}</option>
      {(q.data?.items ?? []).map((p) => (
        <option key={p.id} value={p.id}>{p.code} · {p.title.slice(0, 60)} ({PROJECT_STATUS[p.status]?.label ?? p.status})</option>
      ))}
    </NativeSelect>
  );
}
