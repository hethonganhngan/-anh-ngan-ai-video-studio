import type { FeedbackCase } from "@/types/api";

export type FeedbackDetail = {
  case: FeedbackCase;
  rca: { id: string; whys: { question: string; answer: string }[]; root_cause: string; cause_category: string; evidence_class: string; confidence_pct: number; is_current: boolean; created_at: string }[];
  capa: { id: string; action_type: string; description: string; owner_id: string | null; deadline: string | null; status: string; approved_by: string | null; completed_at: string | null; completion_evidence: { type: string; ref: string; note: string }[]; created_at: string }[];
  verifications: { id: string; method: string; kpi_before: number | null; kpi_after: number | null; passed: boolean; evidence: { ref: string; note: string }[]; notes: string; created_at: string }[];
  events: { id: string; created_at: string; step: string; from_status: string | null; to_status: string; actor_type: string; actor_ref: string | null; note: string }[];
  overdue: boolean;
  allowed_next: string[];
  lesson_id?: string | null;
};

export type FeedbackMeta = {
  statuses: string[]; steps: string[]; sources: string[]; categories: string[]; priorities: string[]; evidence_classes: string[];
};

export const SOURCE_LABEL: Record<string, string> = {
  QC: "Kiểm định QC", CUSTOMER: "Khách hàng", INTERNAL: "Nội bộ", ANALYTICS: "Số liệu sau đăng", AGENT: "AI Agent", PUBLISHING: "Phát hành",
};
export const CATEGORY_LABEL: Record<string, string> = {
  PROMPT: "Prompt", CHARACTER: "Nhân vật", VOICE: "Giọng nói", PROVIDER: "Nhà cung cấp", SCRIPT: "Kịch bản", AUDIO: "Âm thanh",
  VISUAL: "Hình ảnh", BRAND: "Thương hiệu", COMPLIANCE: "Tuân thủ", PROCESS: "Quy trình", ASSET: "Tài nguyên", PERFORMANCE: "Hiệu quả", OTHER: "Khác",
};
export const EVIDENCE_LABEL: Record<string, string> = { FACT: "FACT — có bằng chứng", HYPOTHESIS: "HYPOTHESIS — giả thuyết", UNKNOWN: "UNKNOWN — chưa rõ" };
export const STEPS = [
  { key: "INTAKE", label: "Tiếp nhận", statuses: ["NEW"] },
  { key: "VALIDATE", label: "Xác thực", statuses: ["VALIDATED"] },
  { key: "TRIAGE", label: "Phân loại", statuses: [] as string[] },
  { key: "ROOT CAUSE", label: "Nguyên nhân gốc", statuses: ["RCA_PENDING"] },
  { key: "CAPA", label: "CAPA", statuses: ["ACTION_APPROVED"] },
  { key: "ASSIGN", label: "Giao việc", statuses: ["IN_PROGRESS"] },
  { key: "VERIFY", label: "Kiểm chứng", statuses: ["VERIFY_PENDING", "VERIFIED", "REOPENED"] },
  { key: "STANDARDIZE", label: "Chuẩn hoá", statuses: ["STANDARDIZED", "CLOSED"] },
];
export const STATUS_STEP_INDEX: Record<string, number> = {
  NEW: 0, VALIDATED: 1, RCA_PENDING: 3, ACTION_APPROVED: 4, IN_PROGRESS: 5, VERIFY_PENDING: 6, REOPENED: 6, VERIFIED: 6, STANDARDIZED: 7, CLOSED: 8,
};
