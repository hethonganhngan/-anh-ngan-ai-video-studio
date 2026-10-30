# Danh mục API (sinh tự động từ OpenAPI)

Tổng: **166 endpoint**. Base URL: `/api/v1`. Tài liệu tương tác: `/docs` (Swagger UI).

Xác thực: cookie httpOnly `an_access` + header `X-CSRF-Token` (giá trị cookie `an_csrf`) cho request thay đổi dữ liệu, hoặc `Authorization: Bearer <token>` cho tích hợp máy-máy. Lỗi chuẩn: `{"error": {"code", "message", "details"}}`.

## Auth

| Method | Path | Mô tả |
|---|---|---|
| `POST` | `/api/v1/auth/change-password` | Change Password |
| `POST` | `/api/v1/auth/login` | Login |
| `POST` | `/api/v1/auth/logout` | Logout |
| `GET` | `/api/v1/auth/me` | Me |

## B01 Project Manager

| Method | Path | Mô tả |
|---|---|---|
| `GET` | `/api/v1/projects` | List  |
| `POST` | `/api/v1/projects` | Create |
| `GET` | `/api/v1/projects/channels` | Channels Mini |
| `POST` | `/api/v1/projects/estimate` | Estimate |
| `GET` | `/api/v1/projects/kanban` | Kanban |
| `GET` | `/api/v1/projects/workflow` | Workflow Definition |
| `GET` | `/api/v1/projects/{project_id}` | Get |
| `PATCH` | `/api/v1/projects/{project_id}` | Update |
| `POST` | `/api/v1/projects/{project_id}/advance` | Advance |
| `POST` | `/api/v1/projects/{project_id}/cancel` | Cancel |
| `GET` | `/api/v1/projects/{project_id}/events` | Events |
| `GET` | `/api/v1/projects/{project_id}/overview` | Overview |
| `POST` | `/api/v1/projects/{project_id}/resolve-manual` | Resolve Manual |
| `POST` | `/api/v1/projects/{project_id}/retry` | Retry |

## B02 AI Script Engine

| Method | Path | Mô tả |
|---|---|---|
| `GET` | `/api/v1/projects/{project_id}/script` | Get Script |
| `PUT` | `/api/v1/projects/{project_id}/script` | Save |
| `POST` | `/api/v1/projects/{project_id}/script/approve` | Approve |
| `POST` | `/api/v1/projects/{project_id}/script/ideas` | Ideas |
| `POST` | `/api/v1/projects/{project_id}/script/prompts` | Prompts |
| `POST` | `/api/v1/projects/{project_id}/script/select-idea` | Select Idea |
| `POST` | `/api/v1/projects/{project_id}/script/versions/{version_id}/restore` | Restore |
| `POST` | `/api/v1/projects/{project_id}/script/write` | Write |
| `PATCH` | `/api/v1/scenes/{scene_id}` | Update Scene |

## B03 Character & Voice Manager

| Method | Path | Mô tả |
|---|---|---|
| `POST` | `/api/v1/character-locks/{lock_id}/approve` | Approve Lock |
| `GET` | `/api/v1/characters` | List Characters |
| `POST` | `/api/v1/characters` | Create Character |
| `GET` | `/api/v1/characters/{cid}` | Get Character |
| `PATCH` | `/api/v1/characters/{cid}` | Update Character |
| `POST` | `/api/v1/characters/{cid}/locks` | Create Lock |
| `POST` | `/api/v1/characters/{cid}/references` | Add Reference |
| `GET` | `/api/v1/scene-locks` | List Scene Locks |
| `POST` | `/api/v1/scene-locks` | Create Scene Lock |
| `POST` | `/api/v1/scene-locks/{lock_id}/approve` | Approve Scene Lock |
| `POST` | `/api/v1/voice-locks/{lock_id}/approve` | Approve Voice Lock |
| `GET` | `/api/v1/voices` | List Voices |
| `POST` | `/api/v1/voices` | Create Voice |
| `DELETE` | `/api/v1/voices/{vid}` | Delete Voice |
| `GET` | `/api/v1/voices/{vid}` | Get Voice |
| `PATCH` | `/api/v1/voices/{vid}` | Update Voice |
| `POST` | `/api/v1/voices/{vid}/locks` | Create Voice Lock |

## B04 Prompt Engine

| Method | Path | Mô tả |
|---|---|---|
| `GET` | `/api/v1/prompts/templates` | Templates |
| `GET` | `/api/v1/prompts/templates/{template_id}/versions` | Versions |
| `POST` | `/api/v1/prompts/templates/{template_id}/versions` | Create Version |
| `GET` | `/api/v1/prompts/versions/{version_id}` | Get Version |
| `POST` | `/api/v1/prompts/versions/{version_id}/activate` | Activate |

## B05 Video Generation Manager

| Method | Path | Mô tả |
|---|---|---|
| `GET` | `/api/v1/generation-jobs` | Jobs |
| `POST` | `/api/v1/generation-jobs/{job_id}/cancel` | Cancel |
| `POST` | `/api/v1/jobs/recover` | Recover |
| `POST` | `/api/v1/projects/{project_id}/generate` | Generate |
| `GET` | `/api/v1/projects/{project_id}/production` | Production |
| `POST` | `/api/v1/projects/{project_id}/validate-assets` | Validate Assets |
| `POST` | `/api/v1/scenes/{scene_id}/import-flow` | Import Flow |
| `POST` | `/api/v1/scenes/{scene_id}/regenerate` | Regenerate |
| `POST` | `/api/v1/scenes/{scene_id}/select-output` | Select Output |
| `GET` | `/api/v1/video-providers` | Providers |

## B06 Render Engine

| Method | Path | Mô tả |
|---|---|---|
| `POST` | `/api/v1/projects/{project_id}/render` | Render |
| `GET` | `/api/v1/projects/{project_id}/renders` | Renders |
| `GET` | `/api/v1/projects/{project_id}/timeline` | Get Timeline |
| `PUT` | `/api/v1/projects/{project_id}/timeline` | Save Timeline |
| `POST` | `/api/v1/projects/{project_id}/timeline/reset` | Reset Timeline |
| `POST` | `/api/v1/projects/{project_id}/voiceover/generate` | Generate Voiceover |
| `GET` | `/api/v1/render-jobs` | Render Jobs |

## B07 Quality Control Engine

| Method | Path | Mô tả |
|---|---|---|
| `POST` | `/api/v1/projects/{project_id}/approve` | Approve |
| `GET` | `/api/v1/projects/{project_id}/qc` | Project Qc |
| `POST` | `/api/v1/projects/{project_id}/qc/final` | Final Review |
| `POST` | `/api/v1/projects/{project_id}/qc/scene-check` | Rerun Scene Qc |
| `POST` | `/api/v1/qc-findings/{finding_id}/feedback` | Finding To Feedback |
| `POST` | `/api/v1/qc-findings/{finding_id}/resolve` | Resolve |
| `GET` | `/api/v1/qc/criteria` | Criteria |
| `GET` | `/api/v1/qc/findings` | Findings |
| `GET` | `/api/v1/qc/queue` | Queue |
| `POST` | `/api/v1/scenes/{scene_id}/qc` | Scene Review |

## B08 Feedback Loop Engine

| Method | Path | Mô tả |
|---|---|---|
| `GET` | `/api/v1/feedback` | List  |
| `POST` | `/api/v1/feedback` | Create |
| `POST` | `/api/v1/feedback/capa/{capa_id}/complete` | Complete Capa |
| `GET` | `/api/v1/feedback/meta` | Meta |
| `GET` | `/api/v1/feedback/stats` | Stats |
| `GET` | `/api/v1/feedback/{case_id}` | Detail |
| `POST` | `/api/v1/feedback/{case_id}/capa` | Add Capa |
| `POST` | `/api/v1/feedback/{case_id}/capa/approve` | Approve Capa |
| `POST` | `/api/v1/feedback/{case_id}/close` | Close |
| `POST` | `/api/v1/feedback/{case_id}/rca` | Rca |
| `POST` | `/api/v1/feedback/{case_id}/rca/suggest` | Rca Suggest |
| `POST` | `/api/v1/feedback/{case_id}/restart` | Restart |
| `POST` | `/api/v1/feedback/{case_id}/standardize` | Standardize |
| `POST` | `/api/v1/feedback/{case_id}/start` | Start |
| `POST` | `/api/v1/feedback/{case_id}/submit-verification` | Submit Verification |
| `POST` | `/api/v1/feedback/{case_id}/triage` | Triage |
| `POST` | `/api/v1/feedback/{case_id}/validate` | Validate |
| `POST` | `/api/v1/feedback/{case_id}/verify` | Verify |

## B09 AI Lessons Learned Engine

| Method | Path | Mô tả |
|---|---|---|
| `GET` | `/api/v1/lessons` | Search |
| `POST` | `/api/v1/lessons` | Create |
| `GET` | `/api/v1/lessons/for-project/{project_id}` | For Project |
| `GET` | `/api/v1/lessons/{lid}` | Get |
| `PATCH` | `/api/v1/lessons/{lid}` | Update |
| `POST` | `/api/v1/lessons/{lid}/apply` | Apply |
| `POST` | `/api/v1/lessons/{lid}/review` | Review |
| `POST` | `/api/v1/lessons/{lid}/rollback` | Rollback |
| `POST` | `/api/v1/lessons/{lid}/submit` | Submit |

## B10 Publishing Manager

| Method | Path | Mô tả |
|---|---|---|
| `POST` | `/api/v1/publications` | Create |
| `GET` | `/api/v1/publications/approved-videos` | Approved |
| `GET` | `/api/v1/publications/calendar` | Calendar |
| `POST` | `/api/v1/publications/check-caption` | Check Caption |
| `PATCH` | `/api/v1/publications/{pid}` | Update |
| `POST` | `/api/v1/publications/{pid}/cancel` | Cancel |
| `POST` | `/api/v1/publications/{pid}/export` | Export |
| `POST` | `/api/v1/publications/{pid}/mark-published` | Mark Published |
| `POST` | `/api/v1/publications/{pid}/publish-api` | Publish Api |

## B11 Analytics Engine

| Method | Path | Mô tả |
|---|---|---|
| `GET` | `/api/v1/analytics/export.csv` | Export Csv |
| `POST` | `/api/v1/analytics/import` | Import Csv |
| `GET` | `/api/v1/analytics/insights` | Insights |
| `GET` | `/api/v1/analytics/performance` | Performance |
| `GET` | `/api/v1/dashboard` | Dashboard |
| `GET` | `/api/v1/publications/{pid}/snapshots` | Snapshots |
| `POST` | `/api/v1/publications/{pid}/snapshots` | Add Snapshot |

## B12 Administration & Cost Manager

| Method | Path | Mô tả |
|---|---|---|
| `GET` | `/api/v1/admin/audit-logs` | Audit Logs |
| `GET` | `/api/v1/admin/backups` | Backups |
| `POST` | `/api/v1/admin/backups` | Create Backup |
| `POST` | `/api/v1/admin/backups/restore` | Restore |
| `GET` | `/api/v1/admin/budgets` | Budgets |
| `POST` | `/api/v1/admin/budgets` | Upsert Budget |
| `DELETE` | `/api/v1/admin/budgets/{bid}` | Delete Budget |
| `GET` | `/api/v1/admin/costs` | Costs |
| `GET` | `/api/v1/admin/health` | Health |
| `POST` | `/api/v1/admin/mode` | Set Mode |
| `GET` | `/api/v1/admin/notifications` | Notifications |
| `POST` | `/api/v1/admin/notifications/read-all` | Read All |
| `GET` | `/api/v1/admin/providers` | Providers |
| `PATCH` | `/api/v1/admin/providers/{pid}` | Update Provider |
| `POST` | `/api/v1/admin/providers/{pid}/test` | Test Provider |
| `GET` | `/api/v1/admin/roles` | Roles |
| `GET` | `/api/v1/admin/settings` | Settings |
| `PUT` | `/api/v1/admin/settings/{key}` | Set Setting |
| `GET` | `/api/v1/admin/users` | Users |
| `POST` | `/api/v1/admin/users` | Create User |
| `GET` | `/api/v1/admin/users/directory` | Directory |
| `PATCH` | `/api/v1/admin/users/{uid}` | Update User |

## Health

| Method | Path | Mô tả |
|---|---|---|
| `GET` | `/health` | Health |
| `GET` | `/health/ready` | Ready |
| `GET` | `/metrics` | Metrics |

## M12 Thư viện tài nguyên

| Method | Path | Mô tả |
|---|---|---|
| `GET` | `/api/v1/assets` | List  |
| `POST` | `/api/v1/assets` | Upload |
| `DELETE` | `/api/v1/assets/{asset_id}` | Delete |
| `GET` | `/api/v1/assets/{asset_id}` | Get |
| `PATCH` | `/api/v1/assets/{asset_id}` | Update |
| `GET` | `/api/v1/assets/{asset_id}/content` | Content |
| `GET` | `/api/v1/assets/{asset_id}/versions` | Versions |
| `POST` | `/api/v1/assets/{asset_id}/versions` | New Version |

## M13 Kênh & Brand DNA

| Method | Path | Mô tả |
|---|---|---|
| `GET` | `/api/v1/channels` | List Channels |
| `POST` | `/api/v1/channels` | Create Channel |
| `GET` | `/api/v1/channels/{cid}` | Get Channel |
| `PATCH` | `/api/v1/channels/{cid}` | Update Channel |
| `PUT` | `/api/v1/channels/{cid}/brand` | Update Brand |

## M14 AI Agent Control Center

| Method | Path | Mô tả |
|---|---|---|
| `GET` | `/api/v1/agents` | List Agents |
| `GET` | `/api/v1/agents/executions` | Executions |
| `GET` | `/api/v1/agents/skills` | List Skills |
| `POST` | `/api/v1/agents/skills` | Create Skill |
| `POST` | `/api/v1/agents/skills/import` | Import Skill |
| `DELETE` | `/api/v1/agents/skills/{skill_id}` | Delete Skill |
| `PATCH` | `/api/v1/agents/skills/{skill_id}` | Update Skill |
| `GET` | `/api/v1/agents/{code}` | Get Agent |
| `PATCH` | `/api/v1/agents/{code}` | Update Agent |
