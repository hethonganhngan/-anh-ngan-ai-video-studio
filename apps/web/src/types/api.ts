export type Page<T> = { items: T[]; total: number; page: number; page_size: number };

export type Me = {
  id: string; email: string; full_name: string; role: { code: string; name: string }; permissions: string[];
  must_change_password: boolean; is_demo: boolean; mode: "DEMO" | "PRODUCTION";
};

export type ChannelMini = { id: string; code: string; name: string };

export type Project = {
  id: string; code: string; channel_id: string; channel: ChannelMini; batch_id: string | null; title: string; topic: string;
  objective: string; target_audience: string; duration_sec: number; aspect_ratio: string; style: string; setting: string;
  cta: string; character_ids: string[]; scene_lock_ids: string[]; voice_profile_id: string | null; budget_limit: string;
  automation_level: string; video_provider_code: string; status: string; resume_status: string | null; progress: number;
  owner_id: string | null; created_by: string | null; deadline: string | null; priority: string; last_error: string | null;
  retry_count: number; approved_by: string | null; approved_at: string | null; data_mode: string; created_at: string;
  updated_at: string;
};

export type Dialogue = { speaker: string; text: string };

export type Scene = {
  id: string; project_id: string; order_index: number; title: string; scene_type: string; duration_sec: number;
  action: string; dialogue: Dialogue[]; setting: string; camera: string; lighting: string; sound: string;
  character_ids: string[]; scene_lock_id: string | null; prompt_text: string; prompt_parts: Record<string, string>;
  negative_prompt: string; prompt_version_id: string | null; current_version_no: number; status: string;
  selected_asset_id: string | null; versions: { id: string; version_no: number; snapshot: Record<string, unknown>; change_note: string; created_at: string }[];
};

export type Idea = {
  index: number; title: string; angle: string; hook: string; summary: string; score: number;
  scores: Record<string, number>; compliance_findings: { rule: string; severity: string; match: string; message: string }[];
  scoring_method: string;
};

export type ScriptVersion = {
  id: string; version_no: number; title: string; hook: string; body: string; cta: string; scenes: Record<string, unknown>[];
  source: string; change_note: string; created_at: string; agent_execution_id: string | null;
};

export type ScriptView = {
  project: Project;
  script: { id: string; ideas: Idea[]; selected_idea_index: number | null; current_version_id: string | null; approved_version_id: string | null; status: string; approved_at: string | null } | null;
  current: ScriptVersion | null; versions: ScriptVersion[]; scenes: Scene[];
  check: { errors: string[]; warnings: string[]; compliance: { rule: string; severity: string; match: string; message: string }[] } | null;
};

export type Asset = {
  id: string; asset_type: string; name: string; description: string; mime_type: string; size_bytes: number;
  checksum_sha256: string; duration_sec: number | null; width: number | null; height: number | null;
  media_info: Record<string, unknown>; tags: string[]; usage_rights: string; rights_note: string;
  rights_expires_at: string | null; source: string; version_no: number; parent_asset_id: string | null;
  channel_id: string | null; project_id: string | null; scene_id: string | null; data_mode: string; created_at: string;
};

export type GenerationJob = {
  id: string; project_id: string; scene_id: string; scene_version_no: number; provider_code: string; status: string;
  attempt_no: number; max_retries: number; provider_job_id: string | null; estimated_cost: string; actual_cost: string;
  result_asset_id: string | null; error_code: string | null; error_message: string | null; started_at: string | null;
  finished_at: string | null; created_at: string; log: { at?: string; msg: string }[]; data_mode: string;
};

export type Character = {
  id: string; code: string; channel_id: string | null; name: string; description: string; age_range: string; gender: string;
  appearance: string; outfit: string; expressions: string[]; personality: string; voice_profile_id: string | null;
  active_lock_id: string | null; consent_status: string; usage_rights: string; status: string; data_mode: string;
  references: { id: string; ref_type: string; asset_id: string; version_no: number; note: string; created_at: string }[];
  created_at: string;
};

export type Lock = {
  id: string; version_no: number; lock_data: Record<string, unknown>; status: string; approved_by: string | null;
  approved_at: string | null; retired_at: string | null; change_note: string; created_at: string;
};

export type Voice = {
  id: string; code: string; name: string; accent: string; gender: string; age_range: string; tone: string;
  speaking_rate: string; provider_code: string; provider_voice_id: string | null; audio_reference_asset_id: string | null;
  consent_status: string; consent_document_asset_id: string | null; usage_rights: string; rights_expires_at: string | null;
  active_lock_id: string | null; status: string; data_mode: string; created_at: string;
};

export type SceneLock = {
  id: string; code: string; version_no: number; channel_id: string | null; name: string;
  lock_data: { setting?: string; lighting?: string; props?: string; colors?: string; reference_asset_ids?: string[] };
  status: string; approved_at: string | null; created_at: string;
};

export type Finding = {
  id: string; qc_review_id: string; project_id: string; scene_id: string | null; criterion: string; severity: string;
  description: string; evidence: Record<string, unknown>; status: string; resolution_note: string; resolved_at: string | null;
  feedback_case_id: string | null; created_at: string;
};

export type QCReview = {
  id: string; project_id: string; render_id: string | null; scene_id: string | null; review_type: string;
  reviewer_type: string; reviewer_id: string | null; scores: Record<string, { score: number | null; method: string; note?: string; evidence?: Record<string, unknown> }>;
  total_score: number; pending_manual: string[]; automated_checks: Record<string, unknown>; has_critical: boolean;
  result: string; notes: string; created_at: string;
};

export type Criterion = { key: string; label: string; method: "AUTO" | "ASSISTED" | "MANUAL"; desc: string };

export type FeedbackCase = {
  id: string; code: string; project_id: string | null; scene_id: string | null; channel_id: string | null;
  character_id: string | null; provider_code: string | null; qc_finding_id: string | null; source: string; category: string;
  title: string; description: string; evidence: { type: string; ref: string; note: string; added_at?: string }[];
  evidence_class: string; priority: string | null; status: string; owner_id: string | null; deadline: string | null;
  kpi_name: string | null; kpi_before: number | null; kpi_after: number | null; kpi_target: number | null;
  approver_id: string | null; reopen_count: number; standardization_note: string; closed_at: string | null;
  created_at: string; updated_at: string;
};

export type Lesson = {
  id: string; code: string; feedback_case_id: string | null; lesson_type: string; title: string; lesson: string;
  root_cause: string; capa_summary: string; verification_summary: string; channel_id: string | null;
  character_id: string | null; error_category: string | null; provider_code: string | null; prompt_example: string;
  proposed_change: { template_code?: string; append_negative?: string; append_rule?: string }; tags: string[];
  status: string; version_no: number; history: Record<string, unknown>[]; approved_at: string | null;
  applied_at: string | null; applied_prompt_version_id: string | null; previous_prompt_version_id: string | null;
  rolled_back_at: string | null; created_at: string;
};

export type Publication = {
  id: string; project_id: string; render_id: string | null; channel_id: string; platform: string; caption: string;
  hashtags: string[]; scheduled_at: string | null; published_at: string | null; post_url: string | null; external_id: string | null;
  publish_mode: string; status: string; export_asset_id: string | null; error_message: string | null; data_mode: string;
  created_at: string;
};

export type Kpi = { key: string; label: string; value: number | null; unit: string; formula: string; source: string; note: string };

export type UserDir = { id: string; full_name: string; role: string };
