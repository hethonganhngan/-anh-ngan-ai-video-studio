import type { BadgeVariant } from "@/components/ui/badge";

export const PROJECT_STATUS: Record<string, { label: string; variant: BadgeVariant }> = {
  CREATED: { label: "Khởi tạo", variant: "gray" },
  SCRIPT_GENERATING: { label: "Đang viết kịch bản", variant: "default" },
  SCRIPT_REVIEW: { label: "Chờ duyệt kịch bản", variant: "yellow" },
  STORYBOARD_READY: { label: "Storyboard sẵn sàng", variant: "default" },
  ASSET_VALIDATION: { label: "Kiểm tra tài nguyên", variant: "default" },
  GENERATION_QUEUED: { label: "Chờ tạo cảnh", variant: "default" },
  GENERATING: { label: "Đang tạo cảnh", variant: "purple" },
  SCENE_QC: { label: "QC từng cảnh", variant: "yellow" },
  RENDERING: { label: "Đang render", variant: "purple" },
  FINAL_QC: { label: "QC tổng thể", variant: "yellow" },
  APPROVAL_PENDING: { label: "Chờ phê duyệt", variant: "orange" },
  APPROVED: { label: "Đã duyệt", variant: "green" },
  PUBLISH_QUEUED: { label: "Chờ xuất bản", variant: "green" },
  PUBLISHED: { label: "Đã xuất bản", variant: "green" },
  ANALYTICS_COLLECTION: { label: "Thu thập số liệu", variant: "green" },
  FEEDBACK_REVIEW: { label: "Rà soát phản hồi", variant: "green" },
  FAILED: { label: "Lỗi", variant: "red" },
  CANCELLED: { label: "Đã huỷ", variant: "gray" },
  RETRY_PENDING: { label: "Chờ chạy lại", variant: "orange" },
  NEEDS_MANUAL_ACTION: { label: "Cần xử lý thủ công", variant: "red" },
};

export const JOB_STATUS: Record<string, { label: string; variant: BadgeVariant }> = {
  QUEUED: { label: "Chờ", variant: "gray" },
  SUBMITTED: { label: "Đã gửi", variant: "default" },
  RUNNING: { label: "Đang chạy", variant: "purple" },
  SUCCEEDED: { label: "Thành công", variant: "green" },
  FAILED: { label: "Lỗi", variant: "red" },
  CANCELLED: { label: "Đã huỷ", variant: "gray" },
  NEEDS_MANUAL_ACTION: { label: "Chờ thủ công", variant: "orange" },
  RETRY_PENDING: { label: "Chờ chạy lại", variant: "orange" },
  BLOCKED_BUDGET: { label: "Chặn ngân sách", variant: "red" },
};

export const SCENE_STATUS: Record<string, { label: string; variant: BadgeVariant }> = {
  PLANNED: { label: "Kế hoạch", variant: "gray" },
  PROMPT_READY: { label: "Có prompt", variant: "default" },
  GENERATING: { label: "Đang tạo", variant: "purple" },
  GENERATED: { label: "Đã tạo", variant: "green" },
  QC_PASSED: { label: "QC đạt", variant: "green" },
  QC_FAILED: { label: "QC không đạt", variant: "red" },
  NEEDS_MANUAL: { label: "Chờ thủ công", variant: "orange" },
  GENERATION_FAILED: { label: "Tạo lỗi", variant: "red" },
};

export const FEEDBACK_STATUS: Record<string, { label: string; variant: BadgeVariant }> = {
  NEW: { label: "Mới", variant: "gray" },
  VALIDATED: { label: "Đã xác thực", variant: "default" },
  RCA_PENDING: { label: "Chờ phân tích", variant: "yellow" },
  ACTION_APPROVED: { label: "CAPA đã duyệt", variant: "default" },
  IN_PROGRESS: { label: "Đang thực hiện", variant: "purple" },
  VERIFY_PENDING: { label: "Chờ kiểm chứng", variant: "orange" },
  VERIFIED: { label: "Đã kiểm chứng", variant: "green" },
  STANDARDIZED: { label: "Đã chuẩn hoá", variant: "green" },
  CLOSED: { label: "Đã đóng", variant: "gray" },
  REOPENED: { label: "Mở lại", variant: "red" },
};

export const LESSON_STATUS: Record<string, { label: string; variant: BadgeVariant }> = {
  DRAFT: { label: "Nháp", variant: "gray" },
  PENDING_APPROVAL: { label: "Chờ duyệt", variant: "yellow" },
  APPROVED: { label: "Đã duyệt", variant: "default" },
  APPLIED: { label: "Đã áp dụng", variant: "green" },
  ROLLED_BACK: { label: "Đã rollback", variant: "orange" },
  REJECTED: { label: "Từ chối", variant: "red" },
};

export const LESSON_TYPES: Record<string, string> = {
  RESOLVED_ERROR: "Lỗi đã xử lý", FAILED_PROMPT: "Prompt thất bại", EFFECTIVE_PROMPT: "Prompt hiệu quả",
  GOOD_VOICE_LOCK: "Voice Lock tốt", GOOD_CHARACTER_LOCK: "Character Lock tốt", ROOT_CAUSE: "Nguyên nhân gốc",
  EFFECTIVE_CAPA: "CAPA hiệu quả",
};

export const PUB_STATUS: Record<string, { label: string; variant: BadgeVariant }> = {
  DRAFT: { label: "Nháp", variant: "gray" },
  SCHEDULED: { label: "Đã lên lịch", variant: "default" },
  PUBLISH_QUEUED: { label: "Chờ đăng", variant: "yellow" },
  EXPORTED: { label: "Đã xuất file", variant: "purple" },
  PUBLISHED: { label: "Đã đăng", variant: "green" },
  FAILED: { label: "Lỗi", variant: "red" },
  CANCELLED: { label: "Đã huỷ", variant: "gray" },
};

export const SEVERITY: Record<string, BadgeVariant> = { CRITICAL: "red", MAJOR: "orange", MINOR: "yellow" };
export const PRIORITY: Record<string, BadgeVariant> = { P0: "red", P1: "orange", P2: "yellow", P3: "gray" };
export const PLATFORMS = ["FACEBOOK", "TIKTOK", "YOUTUBE", "ZALO"] as const;
export const AUTOMATION: Record<string, string> = { MANUAL: "Thủ công (từng bước)", ASSISTED: "Hỗ trợ (AI chạy tới cổng duyệt)", AUTO: "Tự động tối đa" };
export const ASSET_TYPES: Record<string, string> = {
  IMAGE: "Ảnh", VIDEO: "Video", AUDIO: "Âm thanh", LOGO: "Logo", CHARACTER: "Nhân vật", BACKGROUND: "Bối cảnh",
  PRODUCT: "Sản phẩm", TEMPLATE: "Template", REFERENCE: "File tham chiếu", SUBTITLE: "Phụ đề", DOCUMENT: "Tài liệu",
  THUMBNAIL: "Thumbnail", EXPORT: "Gói xuất bản",
};
export const USAGE_RIGHTS: Record<string, string> = {
  OWNED: "Sở hữu", LICENSED: "Có giấy phép", CONSENTED: "Có đồng ý", AI_GENERATED: "AI tạo", UNKNOWN: "Chưa rõ",
};
export const label = (map: Record<string, { label: string }>, key?: string | null) => (key ? map[key]?.label ?? key : "—");
