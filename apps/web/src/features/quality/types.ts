import type { Criterion, Finding, Project, QCReview } from "@/types/api";

export type QCView = {
  project: Project;
  render: { id: string; version_no: number; video_asset_id: string; thumbnail_asset_id: string | null; subtitle_asset_id: string | null;
    duration_sec: number; width: number; height: number; status: string; probe: Record<string, unknown> } | null;
  agent_final: QCReview | null;
  reviews: QCReview[];
  findings: Finding[];
  approvals: { id: string; render_id: string | null; approver_id: string; decision: string; comment: string; created_at: string }[];
  criteria: Criterion[];
  policy: { min_total: number; require_human_review: boolean; blocking_severities: string[] };
};
export type QueueItem = Project & { open_findings: number };
