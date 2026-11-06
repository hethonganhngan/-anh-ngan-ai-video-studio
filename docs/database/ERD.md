# Sơ đồ cơ sở dữ liệu (sinh tự động từ SQLAlchemy metadata)

PostgreSQL 16 · **46 bảng** · khoá chính UUID · migration Alembic tại `migrations/`.

```mermaid
erDiagram
  agent_configs {
    varchar code PK
    varchar name
    text role_description
    varchar provider_code
    varchar model
    boolean is_enabled
    jsonb allowed_actions
    varchar prompt_template_code
    integer max_runs_per_day
    numeric max_cost_per_run
    integer max_tokens
    integer timeout_sec
    datetime created_at
    datetime updated_at
  }
  agent_executions {
    varchar agent_code FK
    varchar action
    varchar model
    varchar provider_code
    uuid prompt_version_id FK
    varchar prompt_version_label
    uuid project_id FK
    jsonb input_ref
    jsonb output_ref
    integer input_tokens
    integer output_tokens
    numeric cost
    boolean is_simulated
    integer latency_ms
    varchar status
    text error
    varchar triggered_by
    datetime started_at
    datetime finished_at
    uuid id PK
    varchar data_mode
  }
  agent_skills {
    varchar code
    varchar name
    text description
    text content
    jsonb agent_codes
    boolean is_enabled
    varchar source
    integer sort_order
    uuid id PK
    datetime created_at
    datetime updated_at
  }
  analytics_snapshots {
    uuid publication_id FK
    uuid project_id FK
    datetime captured_at
    integer views
    integer likes
    integer comments
    integer shares
    integer saves
    float retention_rate
    float avg_watch_sec
    integer conversions
    varchar source
    uuid entered_by FK
    uuid id PK
    datetime created_at
    datetime updated_at
    varchar data_mode
  }
  approvals {
    uuid project_id FK
    uuid render_id FK
    uuid qc_review_id FK
    uuid approver_id FK
    varchar decision
    text comment
    uuid id PK
    datetime created_at
    datetime updated_at
    varchar data_mode
  }
  assets {
    varchar asset_type
    varchar name
    text description
    varchar storage_backend
    varchar storage_key
    varchar mime_type
    bigint size_bytes
    varchar checksum_sha256
    float duration_sec
    integer width
    integer height
    jsonb media_info
    jsonb tags
    varchar usage_rights
    text rights_note
    datetime rights_expires_at
    varchar source
    integer version_no
    uuid parent_asset_id FK
    uuid channel_id FK
    uuid project_id FK
    uuid scene_id FK
    uuid uploaded_by FK
    uuid id PK
    datetime created_at
    datetime updated_at
    datetime deleted_at
    varchar data_mode
  }
  audit_logs {
    datetime created_at
    varchar actor_type
    varchar actor_id
    varchar actor_label
    varchar action
    varchar entity_type
    varchar entity_id
    jsonb before
    jsonb after
    varchar ip_address
    varchar user_agent
    varchar data_mode
    uuid id PK
  }
  backups {
    varchar file_name
    integer size_bytes
    varchar status
    varchar checksum
    uuid created_by FK
    varchar note
    datetime restored_at
    uuid id PK
    datetime created_at
    datetime updated_at
  }
  brand_profiles {
    uuid channel_id FK
    varchar slogan
    varchar brand_promise
    varchar big_idea
    jsonb brand_voice
    text audience
    jsonb content_pillars
    jsonb character_set
    jsonb voice_set
    jsonb scene_set
    jsonb cta_rules
    jsonb quality_rules
    jsonb publishing_rules
    jsonb forbidden_terms
    integer version_no
    jsonb history
    uuid updated_by FK
    uuid id PK
    datetime created_at
    datetime updated_at
  }
  budget_limits {
    varchar scope
    varchar scope_ref
    varchar period
    numeric limit_amount
    integer alert_threshold_pct
    boolean hard_stop
    varchar data_mode
    uuid id PK
    datetime created_at
    datetime updated_at
  }
  capa_actions {
    uuid feedback_case_id FK
    varchar action_type
    text description
    uuid owner_id FK
    datetime deadline
    varchar status
    uuid approved_by FK
    datetime approved_at
    datetime completed_at
    jsonb completion_evidence
    uuid id PK
    datetime created_at
    datetime updated_at
  }
  channels {
    varchar code
    varchar name
    text description
    jsonb platforms
    boolean is_active
    uuid id PK
    datetime created_at
    datetime updated_at
    datetime deleted_at
  }
  character_locks {
    uuid character_id FK
    integer version_no
    jsonb lock_data
    varchar status
    uuid created_by FK
    uuid approved_by FK
    datetime approved_at
    datetime retired_at
    varchar change_note
    uuid id PK
    datetime created_at
    datetime updated_at
  }
  character_references {
    uuid character_id FK
    varchar ref_type
    uuid asset_id FK
    integer version_no
    varchar note
    uuid id PK
    datetime created_at
    datetime updated_at
  }
  characters {
    varchar code
    uuid channel_id FK
    varchar name
    text description
    varchar age_range
    varchar gender
    text appearance
    text outfit
    jsonb expressions
    text personality
    uuid voice_profile_id FK
    uuid active_lock_id FK
    varchar consent_status
    text usage_rights
    varchar status
    uuid id PK
    datetime created_at
    datetime updated_at
    datetime deleted_at
    varchar data_mode
  }
  cost_records {
    datetime created_at
    uuid project_id FK
    uuid channel_id FK
    uuid scene_id FK
    uuid generation_job_id FK
    uuid agent_execution_id FK
    varchar category
    varchar provider_code
    numeric quantity
    varchar unit
    numeric amount
    boolean is_simulated
    varchar description
    uuid id PK
    varchar data_mode
  }
  feedback_cases {
    varchar code
    uuid project_id FK
    uuid scene_id FK
    uuid channel_id FK
    uuid character_id FK
    varchar provider_code
    uuid qc_finding_id FK
    varchar source
    varchar category
    varchar title
    text description
    jsonb evidence
    varchar evidence_class
    varchar priority
    varchar status
    uuid owner_id FK
    datetime deadline
    varchar kpi_name
    float kpi_before
    float kpi_after
    float kpi_target
    uuid approver_id FK
    uuid reported_by FK
    integer reopen_count
    text standardization_note
    datetime closed_at
    uuid id PK
    datetime created_at
    datetime updated_at
    varchar data_mode
  }
  feedback_events {
    datetime created_at
    uuid feedback_case_id FK
    varchar step
    varchar from_status
    varchar to_status
    varchar actor_type
    varchar actor_ref
    text note
    uuid id PK
  }
  generation_jobs {
    uuid project_id FK
    uuid scene_id FK
    integer scene_version_no
    varchar provider_code
    varchar status
    integer attempt_no
    integer max_retries
    varchar provider_job_id
    jsonb prompt_snapshot
    numeric estimated_cost
    numeric actual_cost
    uuid result_asset_id FK
    varchar error_code
    text error_message
    varchar idempotency_key
    varchar celery_task_id
    uuid requested_by FK
    datetime started_at
    datetime finished_at
    jsonb log
    uuid id PK
    datetime created_at
    datetime updated_at
    varchar data_mode
  }
  lessons_learned {
    varchar code
    uuid feedback_case_id FK
    varchar lesson_type
    varchar title
    text lesson
    text root_cause
    text capa_summary
    text verification_summary
    uuid channel_id FK
    uuid character_id FK
    varchar error_category
    varchar provider_code
    text prompt_example
    jsonb proposed_change
    jsonb tags
    varchar status
    integer version_no
    jsonb history
    uuid created_by FK
    uuid approved_by FK
    datetime approved_at
    datetime applied_at
    uuid applied_prompt_version_id FK
    uuid previous_prompt_version_id FK
    datetime rolled_back_at
    uuid id PK
    datetime created_at
    datetime updated_at
    varchar data_mode
  }
  notifications {
    uuid user_id FK
    varchar level
    varchar category
    varchar title
    text message
    varchar link
    datetime read_at
    varchar data_mode
    uuid id PK
    datetime created_at
    datetime updated_at
  }
  permissions {
    varchar code
    varchar description
    uuid id PK
    datetime created_at
    datetime updated_at
  }
  production_batches {
    varchar code
    uuid channel_id FK
    varchar title
    integer quantity
    uuid created_by FK
    varchar idempotency_key
    uuid id PK
    datetime created_at
    datetime updated_at
    varchar data_mode
  }
  projects {
    varchar code
    uuid channel_id FK
    uuid batch_id FK
    varchar title
    text topic
    text objective
    text target_audience
    integer duration_sec
    varchar aspect_ratio
    varchar style
    varchar setting
    varchar cta
    jsonb character_ids
    jsonb scene_lock_ids
    uuid voice_profile_id FK
    numeric budget_limit
    varchar automation_level
    varchar video_provider_code
    varchar status
    varchar resume_status
    integer progress
    uuid owner_id FK
    uuid created_by FK
    datetime deadline
    varchar priority
    varchar idempotency_key
    jsonb timeline
    text last_error
    integer retry_count
    uuid approved_by FK
    datetime approved_at
    uuid id PK
    datetime created_at
    datetime updated_at
    datetime deleted_at
    varchar data_mode
  }
  prompt_templates {
    varchar code
    varchar name
    varchar agent_code
    text purpose
    uuid channel_id FK
    uuid active_version_id FK
    uuid demo_active_version_id FK
    uuid id PK
    datetime created_at
    datetime updated_at
  }
  prompt_versions {
    uuid template_id FK
    integer version_no
    text content
    text negative_prompt
    jsonb rules
    varchar status
    varchar data_mode
    varchar change_note
    uuid source_lesson_id FK
    uuid created_by FK
    uuid approved_by FK
    datetime approved_at
    uuid id PK
    datetime created_at
    datetime updated_at
  }
  provider_accounts {
    varchar provider_type
    varchar provider_code
    varchar name
    boolean is_enabled
    jsonb config
    text secret_encrypted
    varchar secret_last4
    varchar connection_status
    datetime last_verified_at
    text last_error
    numeric unit_cost
    varchar cost_unit
    uuid id PK
    datetime created_at
    datetime updated_at
  }
  publications {
    uuid project_id FK
    uuid render_id FK
    uuid channel_id FK
    varchar platform
    text caption
    jsonb hashtags
    datetime scheduled_at
    datetime published_at
    varchar post_url
    varchar publish_mode
    varchar status
    uuid export_asset_id FK
    text error_message
    uuid created_by FK
    uuid published_by FK
    uuid id PK
    datetime created_at
    datetime updated_at
    varchar data_mode
  }
  qc_findings {
    uuid qc_review_id FK
    uuid project_id FK
    uuid scene_id FK
    varchar criterion
    varchar severity
    text description
    jsonb evidence
    varchar status
    uuid resolved_by FK
    datetime resolved_at
    text resolution_note
    uuid feedback_case_id FK
    uuid id PK
    datetime created_at
    datetime updated_at
  }
  qc_reviews {
    uuid project_id FK
    uuid render_id FK
    uuid scene_id FK
    varchar review_type
    varchar reviewer_type
    uuid reviewer_id FK
    jsonb scores
    float total_score
    jsonb pending_manual
    jsonb automated_checks
    boolean has_critical
    varchar result
    text notes
    uuid agent_execution_id FK
    uuid id PK
    datetime created_at
    datetime updated_at
    varchar data_mode
  }
  render_jobs {
    uuid project_id FK
    varchar status
    jsonb timeline
    integer attempt_no
    integer max_retries
    varchar idempotency_key
    varchar celery_task_id
    text error_message
    jsonb log
    uuid requested_by FK
    datetime started_at
    datetime finished_at
    uuid id PK
    datetime created_at
    datetime updated_at
    varchar data_mode
  }
  renders {
    uuid project_id FK
    uuid render_job_id FK
    integer version_no
    uuid video_asset_id FK
    uuid thumbnail_asset_id FK
    uuid subtitle_asset_id FK
    float duration_sec
    integer width
    integer height
    bigint size_bytes
    jsonb probe
    varchar status
    text notes
    uuid id PK
    datetime created_at
    datetime updated_at
    varchar data_mode
  }
  role_permissions {
    uuid role_id PK
    uuid permission_id PK
  }
  roles {
    varchar code
    varchar name
    varchar description
    uuid id PK
    datetime created_at
    datetime updated_at
  }
  root_cause_analyses {
    uuid feedback_case_id FK
    jsonb whys
    text root_cause
    varchar cause_category
    varchar evidence_class
    integer confidence_pct
    varchar created_by_type
    uuid created_by FK
    boolean is_current
    uuid id PK
    datetime created_at
    datetime updated_at
  }
  scene_locks {
    varchar code
    integer version_no
    uuid channel_id FK
    varchar name
    jsonb lock_data
    varchar status
    uuid created_by FK
    uuid approved_by FK
    datetime approved_at
    datetime retired_at
    uuid id PK
    datetime created_at
    datetime updated_at
    varchar data_mode
  }
  scene_versions {
    uuid scene_id FK
    integer version_no
    jsonb snapshot
    text prompt_text
    text negative_prompt
    varchar change_note
    uuid created_by FK
    uuid id PK
    datetime created_at
    datetime updated_at
  }
  scenes {
    uuid project_id FK
    integer order_index
    varchar title
    varchar scene_type
    integer duration_sec
    text action
    jsonb dialogue
    text setting
    varchar camera
    varchar lighting
    varchar sound
    jsonb character_ids
    uuid scene_lock_id FK
    text prompt_text
    jsonb prompt_parts
    text negative_prompt
    uuid prompt_version_id FK
    integer current_version_no
    varchar status
    uuid selected_asset_id FK
    uuid id PK
    datetime created_at
    datetime updated_at
    varchar data_mode
  }
  script_versions {
    uuid script_id FK
    integer version_no
    varchar title
    text hook
    text body
    varchar cta
    jsonb scenes
    varchar source
    varchar change_note
    uuid created_by FK
    uuid agent_execution_id FK
    uuid id PK
    datetime created_at
    datetime updated_at
  }
  scripts {
    uuid project_id FK
    jsonb ideas
    integer selected_idea_index
    uuid current_version_id FK
    varchar status
    uuid approved_version_id FK
    uuid approved_by FK
    datetime approved_at
    uuid id PK
    datetime created_at
    datetime updated_at
    varchar data_mode
  }
  system_settings {
    varchar key PK
    jsonb value
    uuid updated_by FK
    datetime created_at
    datetime updated_at
  }
  users {
    varchar email
    varchar full_name
    varchar password_hash
    uuid role_id FK
    boolean is_active
    boolean must_change_password
    integer failed_login_count
    datetime locked_until
    datetime last_login_at
    boolean is_demo
    uuid id PK
    datetime created_at
    datetime updated_at
    datetime deleted_at
  }
  verification_results {
    uuid feedback_case_id FK
    text method
    float kpi_before
    float kpi_after
    boolean passed
    jsonb evidence
    text notes
    uuid verified_by FK
    uuid id PK
    datetime created_at
    datetime updated_at
  }
  voice_locks {
    uuid voice_profile_id FK
    integer version_no
    jsonb lock_data
    varchar status
    uuid created_by FK
    uuid approved_by FK
    datetime approved_at
    datetime retired_at
    varchar change_note
    uuid id PK
    datetime created_at
    datetime updated_at
  }
  voice_profiles {
    varchar code
    varchar name
    varchar accent
    varchar gender
    varchar age_range
    varchar tone
    varchar speaking_rate
    varchar provider_code
    varchar provider_voice_id
    uuid audio_reference_asset_id FK
    varchar consent_status
    uuid consent_document_asset_id FK
    text usage_rights
    datetime rights_expires_at
    uuid active_lock_id FK
    varchar status
    uuid id PK
    datetime created_at
    datetime updated_at
    datetime deleted_at
    varchar data_mode
  }
  workflow_events {
    datetime created_at
    uuid project_id FK
    varchar from_status
    varchar to_status
    varchar actor_type
    varchar actor_ref
    text note
    jsonb payload
    uuid id PK
  }
  agent_configs ||--o{ agent_executions : "agent_code"
  agent_executions ||--o{ cost_records : "agent_execution_id"
  agent_executions ||--o{ qc_reviews : "agent_execution_id"
  agent_executions ||--o{ script_versions : "agent_execution_id"
  assets ||--o{ character_references : "asset_id"
  assets ||--o{ generation_jobs : "result_asset_id"
  assets ||--o{ publications : "export_asset_id"
  assets ||--o{ renders : "subtitle_asset_id"
  assets ||--o{ renders : "thumbnail_asset_id"
  assets ||--o{ renders : "video_asset_id"
  assets ||--o{ scenes : "selected_asset_id"
  assets ||--o{ voice_profiles : "audio_reference_asset_id"
  assets ||--o{ voice_profiles : "consent_document_asset_id"
  channels ||--o{ assets : "channel_id"
  channels ||--o{ brand_profiles : "channel_id"
  channels ||--o{ characters : "channel_id"
  channels ||--o{ cost_records : "channel_id"
  channels ||--o{ feedback_cases : "channel_id"
  channels ||--o{ lessons_learned : "channel_id"
  channels ||--o{ production_batches : "channel_id"
  channels ||--o{ projects : "channel_id"
  channels ||--o{ prompt_templates : "channel_id"
  channels ||--o{ publications : "channel_id"
  channels ||--o{ scene_locks : "channel_id"
  character_locks ||--o{ characters : "active_lock_id"
  characters ||--o{ character_locks : "character_id"
  characters ||--o{ character_references : "character_id"
  characters ||--o{ feedback_cases : "character_id"
  characters ||--o{ lessons_learned : "character_id"
  feedback_cases ||--o{ capa_actions : "feedback_case_id"
  feedback_cases ||--o{ feedback_events : "feedback_case_id"
  feedback_cases ||--o{ lessons_learned : "feedback_case_id"
  feedback_cases ||--o{ qc_findings : "feedback_case_id"
  feedback_cases ||--o{ root_cause_analyses : "feedback_case_id"
  feedback_cases ||--o{ verification_results : "feedback_case_id"
  generation_jobs ||--o{ cost_records : "generation_job_id"
  lessons_learned ||--o{ prompt_versions : "source_lesson_id"
  permissions ||--o{ role_permissions : "permission_id"
  production_batches ||--o{ projects : "batch_id"
  projects ||--o{ agent_executions : "project_id"
  projects ||--o{ analytics_snapshots : "project_id"
  projects ||--o{ approvals : "project_id"
  projects ||--o{ assets : "project_id"
  projects ||--o{ cost_records : "project_id"
  projects ||--o{ feedback_cases : "project_id"
  projects ||--o{ generation_jobs : "project_id"
  projects ||--o{ publications : "project_id"
  projects ||--o{ qc_findings : "project_id"
  projects ||--o{ qc_reviews : "project_id"
  projects ||--o{ render_jobs : "project_id"
  projects ||--o{ renders : "project_id"
  projects ||--o{ scenes : "project_id"
  projects ||--o{ scripts : "project_id"
  projects ||--o{ workflow_events : "project_id"
  prompt_templates ||--o{ prompt_versions : "template_id"
  prompt_versions ||--o{ agent_executions : "prompt_version_id"
  prompt_versions ||--o{ lessons_learned : "applied_prompt_version_id"
  prompt_versions ||--o{ lessons_learned : "previous_prompt_version_id"
  prompt_versions ||--o{ prompt_templates : "active_version_id"
  prompt_versions ||--o{ prompt_templates : "demo_active_version_id"
  prompt_versions ||--o{ scenes : "prompt_version_id"
  publications ||--o{ analytics_snapshots : "publication_id"
  qc_findings ||--o{ feedback_cases : "qc_finding_id"
  qc_reviews ||--o{ approvals : "qc_review_id"
  qc_reviews ||--o{ qc_findings : "qc_review_id"
  render_jobs ||--o{ renders : "render_job_id"
  renders ||--o{ approvals : "render_id"
  renders ||--o{ publications : "render_id"
  renders ||--o{ qc_reviews : "render_id"
  roles ||--o{ role_permissions : "role_id"
  roles ||--o{ users : "role_id"
  scene_locks ||--o{ scenes : "scene_lock_id"
  scenes ||--o{ assets : "scene_id"
  scenes ||--o{ cost_records : "scene_id"
  scenes ||--o{ feedback_cases : "scene_id"
  scenes ||--o{ generation_jobs : "scene_id"
  scenes ||--o{ qc_findings : "scene_id"
  scenes ||--o{ qc_reviews : "scene_id"
  scenes ||--o{ scene_versions : "scene_id"
  script_versions ||--o{ scripts : "approved_version_id"
  script_versions ||--o{ scripts : "current_version_id"
  scripts ||--o{ script_versions : "script_id"
  users ||--o{ analytics_snapshots : "entered_by"
  users ||--o{ approvals : "approver_id"
  users ||--o{ assets : "uploaded_by"
  users ||--o{ backups : "created_by"
  users ||--o{ brand_profiles : "updated_by"
  users ||--o{ capa_actions : "approved_by"
  users ||--o{ capa_actions : "owner_id"
  users ||--o{ character_locks : "approved_by"
  users ||--o{ character_locks : "created_by"
  users ||--o{ feedback_cases : "approver_id"
  users ||--o{ feedback_cases : "owner_id"
  users ||--o{ feedback_cases : "reported_by"
  users ||--o{ generation_jobs : "requested_by"
  users ||--o{ lessons_learned : "approved_by"
  users ||--o{ lessons_learned : "created_by"
  users ||--o{ notifications : "user_id"
  users ||--o{ production_batches : "created_by"
  users ||--o{ projects : "approved_by"
  users ||--o{ projects : "created_by"
  users ||--o{ projects : "owner_id"
  users ||--o{ prompt_versions : "approved_by"
  users ||--o{ prompt_versions : "created_by"
  users ||--o{ publications : "created_by"
  users ||--o{ publications : "published_by"
  users ||--o{ qc_findings : "resolved_by"
  users ||--o{ qc_reviews : "reviewer_id"
  users ||--o{ render_jobs : "requested_by"
  users ||--o{ root_cause_analyses : "created_by"
  users ||--o{ scene_locks : "approved_by"
  users ||--o{ scene_locks : "created_by"
  users ||--o{ scene_versions : "created_by"
  users ||--o{ script_versions : "created_by"
  users ||--o{ scripts : "approved_by"
  users ||--o{ system_settings : "updated_by"
  users ||--o{ verification_results : "verified_by"
  users ||--o{ voice_locks : "approved_by"
  users ||--o{ voice_locks : "created_by"
  voice_locks ||--o{ voice_profiles : "active_lock_id"
  voice_profiles ||--o{ characters : "voice_profile_id"
  voice_profiles ||--o{ projects : "voice_profile_id"
  voice_profiles ||--o{ voice_locks : "voice_profile_id"
```

## Danh sách bảng

| Bảng | Số cột | Ghi chú |
|---|---|---|
| `agent_configs` | 14 |  |
| `agent_executions` | 21 | tách DEMO/PRODUCTION |
| `agent_skills` | 11 |  |
| `analytics_snapshots` | 17 | tách DEMO/PRODUCTION |
| `approvals` | 10 | tách DEMO/PRODUCTION |
| `assets` | 28 | tách DEMO/PRODUCTION, soft delete, có phiên bản |
| `audit_logs` | 13 | tách DEMO/PRODUCTION, append-only (trigger) |
| `backups` | 10 |  |
| `brand_profiles` | 20 | có phiên bản |
| `budget_limits` | 10 | tách DEMO/PRODUCTION |
| `capa_actions` | 13 |  |
| `channels` | 9 | soft delete |
| `character_locks` | 12 | có phiên bản, bất biến sau duyệt (trigger) |
| `character_references` | 8 | có phiên bản |
| `characters` | 20 | tách DEMO/PRODUCTION, soft delete |
| `cost_records` | 15 | tách DEMO/PRODUCTION |
| `feedback_cases` | 30 | tách DEMO/PRODUCTION |
| `feedback_events` | 9 |  |
| `generation_jobs` | 24 | tách DEMO/PRODUCTION |
| `lessons_learned` | 29 | tách DEMO/PRODUCTION, có phiên bản |
| `notifications` | 11 | tách DEMO/PRODUCTION |
| `permissions` | 5 |  |
| `production_batches` | 10 | tách DEMO/PRODUCTION |
| `projects` | 36 | tách DEMO/PRODUCTION, soft delete |
| `prompt_templates` | 10 |  |
| `prompt_versions` | 15 | tách DEMO/PRODUCTION, có phiên bản, bất biến sau duyệt (trigger) |
| `provider_accounts` | 15 |  |
| `publications` | 19 | tách DEMO/PRODUCTION |
| `qc_findings` | 15 |  |
| `qc_reviews` | 18 | tách DEMO/PRODUCTION |
| `render_jobs` | 16 | tách DEMO/PRODUCTION |
| `renders` | 17 | tách DEMO/PRODUCTION, có phiên bản |
| `role_permissions` | 2 |  |
| `roles` | 6 |  |
| `root_cause_analyses` | 12 |  |
| `scene_locks` | 14 | tách DEMO/PRODUCTION, có phiên bản, bất biến sau duyệt (trigger) |
| `scene_versions` | 10 | có phiên bản |
| `scenes` | 24 | tách DEMO/PRODUCTION |
| `script_versions` | 14 | có phiên bản, bất biến sau duyệt (trigger) |
| `scripts` | 12 | tách DEMO/PRODUCTION |
| `system_settings` | 5 |  |
| `users` | 14 | soft delete |
| `verification_results` | 11 |  |
| `voice_locks` | 12 | có phiên bản, bất biến sau duyệt (trigger) |
| `voice_profiles` | 21 | tách DEMO/PRODUCTION, soft delete |
| `workflow_events` | 9 |  |
