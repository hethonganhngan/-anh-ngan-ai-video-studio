import { Badge, type BadgeVariant } from "@/components/ui/badge";

export function StatusBadge({ map, value }: { map: Record<string, { label: string; variant: BadgeVariant }>; value?: string | null }) {
  if (!value) return <Badge variant="gray">—</Badge>;
  const m = map[value];
  return <Badge variant={m?.variant ?? "gray"} data-status={value}>{m?.label ?? value}</Badge>;
}

export function ModeBadge({ mode }: { mode?: string }) {
  return mode === "PRODUCTION"
    ? <Badge variant="green" data-testid="mode-badge">PRODUCTION</Badge>
    : <Badge variant="yellow" data-testid="mode-badge">DEMO — dữ liệu mẫu</Badge>;
}
