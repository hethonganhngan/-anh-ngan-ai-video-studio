# Tiêu chí nghiệm thu & bằng chứng kiểm thử

## A. 20 hạng mục kiểm thử bắt buộc

| # | Hạng mục | Kiểm thử tự động |
|---|---|---|
| 1 | Đăng nhập | `test_auth_rbac::test_login_wrong_password_and_lockout`, `test_cookie_auth_requires_csrf`; E2E `m00` |
| 2 | RBAC | `test_auth_rbac::test_rbac_matrix` (10 ca), `test_creator_cannot_approve_script_or_publish`; unit `test_rbac_catalog_integrity`; E2E `m00`, `m15` |
| 3 | Tạo dự án | `test_generation::test_idempotent_project_creation_and_batch`, `test_validation_rejects_bad_brief`; E2E `m02` |
| 4 | Tạo kịch bản | `test_end_to_end`; unit `test_mock_script_respects_scene_rules`; E2E `m03` |
| 5 | Chia storyboard | `test_end_to_end` (cảnh 8s, ≤ 2 thoại, prompt 9 phần); unit `test_scene_rules_*`; E2E `m03` |
| 6 | Quản lý nhân vật | `test_characters` (7 ca); E2E `m04` |
| 7 | Tạo cảnh Mock | `test_end_to_end`, `test_generation`; E2E `m05` |
| 8 | Nhập cảnh Flow | `test_generation::test_manual_flow_import`; E2E `m05` |
| 9 | Render MP4 thật | `test_render_quality::test_editor_timeline_full_render`, `test_render_real_1080p`; E2E `m06` |
| 10 | QC | `test_render_quality::test_final_qc_rules_and_approval`; E2E `m07` |
| 11 | Phê duyệt | `test_end_to_end`, `test_final_qc_rules_and_approval`; E2E `m07` |
| 12 | Feedback Loop | `test_feedback_lessons::test_feedback_full_loop_with_reopen`; E2E `m08` |
| 13 | CAPA | `test_feedback_lessons` (duyệt 4 mắt, hoàn thành cần bằng chứng); E2E `m08` |
| 14 | Lessons Learned | `test_lesson_approve_apply_rollback_changes_prompt`, `test_lesson_manual_and_edit_versions`; E2E `m09` |
| 15 | Publishing Calendar | `test_end_to_end`, `test_publishing_analytics`; E2E `m10` |
| 16 | Analytics | `test_publishing_analytics::test_multi_platform_csv_insights_export`; E2E `m10`, `m01` |
| 17 | Agent Logs | `test_admin_agents::test_agents_registry_and_execution_logs`; E2E `m14` |
| 18 | Cost Limits | `test_generation::test_budget_exceeded_blocks_generation`, `test_global_budget_hard_stop`; E2E `m15` |
| 19 | Retry | `test_generation::test_fail_once_then_auto_retry_succeeds`, `test_render_failure_retry_and_failed_state`; E2E `m11` |
| 20 | Backup/Restore | `test_admin_agents::test_backup_and_restore_round_trip`; E2E `m15` |

## B. Kiểm thử lỗi

| Tình huống | Kiểm thử |
|---|---|
| API timeout | `test_provider_unavailable_and_timeout_are_retried` (`[[MOCK_TIMEOUT]]`), Mock LLM `[[MOCK_LLM_TIMEOUT]]` |
| File không hợp lệ | `test_manual_flow_import` (sai tỉ lệ, file giả mạo), E2E `m12` (.png giả) |
| Duplicate Job | `test_duplicate_job_is_rejected`, `test_concurrent_duplicate_requests_return_same_project` |
| Worker restart | `test_worker_restart_recovery`; kiểm chứng thủ công với Celery worker thật (PROJECT_STATUS) |
| Budget exceeded | `test_budget_exceeded_blocks_generation`, `test_global_budget_hard_stop` |
| Unauthorized approval | `test_end_to_end` (QC/Publisher → 403), `test_rbac_matrix` (System Admin → 403) |
| QC failed | `test_end_to_end` (< 98 → FAIL), `test_final_qc_rules_and_approval` (CRITICAL mở → FAIL) |
| Missing asset | `test_unlocked_character_blocks_generation`, kiểm tra checksum ảnh Lock trong `validate_assets` |
| Provider unavailable | `test_provider_unavailable_and_timeout_are_retried`, `test_real_provider_blocked_in_demo_and_mock_blocked_in_production` |
| Rollback | `test_lesson_approve_apply_rollback_changes_prompt` (+ xung đột rollback), `test_backup_and_restore_round_trip` |

## C. 18 điều kiện bàn giao

| # | Điều kiện | Bằng chứng |
|---|---|---|
| 1 | Đủ 15 màn hình | Sidebar 15 mục (E2E `m00`), FEATURE_MATRIX |
| 2 | 12 Backend Module | `services/api/app/modules/*` (12 thư mục) |
| 3 | 10 Agent Roles | `agents/registry.py`, `test_agents_registry_and_execution_logs` |
| 4 | Database hoạt động | Alembic up/down, `alembic check`, 45 bảng |
| 5 | Workflow hoạt động | `test_end_to_end` đi qua 15 trạng thái chính; unit state machine |
| 6 | Tạo video thử nghiệm | Mock provider → MP4 thật |
| 7 | Nhập video từ Flow | `test_manual_flow_import` |
| 8 | Render MP4 thực tế | 540p (test nhanh) + 1080×1920 H.264/AAC 30fps |
| 9 | QC & phê duyệt | M07 tests |
| 10 | Feedback Loop | M08 tests |
| 11 | Lessons Learned | M09 tests |
| 12 | Quản lý chi phí | Budget tests, cost_records, Dashboard cảnh báo |
| 13 | Phân quyền | RBAC tests |
| 14 | Audit log | append-only trigger test, audit cho mọi thao tác ghi |
| 15 | Kiểm thử | pytest + Playwright (PROJECT_STATUS) |
| 16 | Tài liệu triển khai | `docs/deployment/` |
| 17 | Hướng dẫn sử dụng | `docs/user-guide/` |
| 18 | Không lỗi nghiêm trọng chưa xử lý | ACCEPTANCE_REPORT — mục "Lỗi tồn đọng" |
