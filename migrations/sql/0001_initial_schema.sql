-- Đóng băng từ SQLAlchemy metadata. KHÔNG sửa; tạo migration mới cho thay đổi.
CREATE TABLE permissions (
	code VARCHAR(80) NOT NULL, 
	description VARCHAR(255) NOT NULL, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_permissions PRIMARY KEY (id), 
	CONSTRAINT uq_permissions_code UNIQUE (code)
);

CREATE TABLE roles (
	code VARCHAR(50) NOT NULL, 
	name VARCHAR(120) NOT NULL, 
	description VARCHAR(255) NOT NULL, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_roles PRIMARY KEY (id), 
	CONSTRAINT uq_roles_code UNIQUE (code)
);

CREATE TABLE audit_logs (
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	actor_type VARCHAR(16) NOT NULL, 
	actor_id VARCHAR(64), 
	actor_label VARCHAR(160), 
	action VARCHAR(80) NOT NULL, 
	entity_type VARCHAR(60) NOT NULL, 
	entity_id VARCHAR(64), 
	before JSONB, 
	after JSONB, 
	ip_address VARCHAR(64), 
	user_agent VARCHAR(255), 
	data_mode VARCHAR(16) NOT NULL, 
	id UUID NOT NULL, 
	CONSTRAINT pk_audit_logs PRIMARY KEY (id)
);

CREATE INDEX ix_audit_logs_created_at ON audit_logs (created_at);

CREATE INDEX ix_audit_logs_action ON audit_logs (action);

CREATE INDEX ix_audit_logs_entity_id ON audit_logs (entity_id);

CREATE INDEX ix_audit_logs_entity_type ON audit_logs (entity_type);

CREATE INDEX ix_audit_logs_actor_id ON audit_logs (actor_id);

CREATE TABLE provider_accounts (
	provider_type VARCHAR(20) NOT NULL, 
	provider_code VARCHAR(60) NOT NULL, 
	name VARCHAR(160) NOT NULL, 
	is_enabled BOOLEAN NOT NULL, 
	config JSONB NOT NULL, 
	secret_encrypted TEXT, 
	secret_last4 VARCHAR(8), 
	connection_status VARCHAR(32) NOT NULL, 
	last_verified_at TIMESTAMP WITH TIME ZONE, 
	last_error TEXT, 
	unit_cost NUMERIC(16, 2) NOT NULL, 
	cost_unit VARCHAR(30) NOT NULL, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_provider_accounts PRIMARY KEY (id), 
	CONSTRAINT uq_provider_accounts_provider_code UNIQUE (provider_code)
);

CREATE TABLE budget_limits (
	scope VARCHAR(20) NOT NULL, 
	scope_ref VARCHAR(64) NOT NULL, 
	period VARCHAR(10) NOT NULL, 
	limit_amount NUMERIC(16, 2) NOT NULL, 
	alert_threshold_pct INTEGER NOT NULL, 
	hard_stop BOOLEAN NOT NULL, 
	data_mode VARCHAR(16) NOT NULL, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_budget_limits PRIMARY KEY (id), 
	CONSTRAINT budget_scope UNIQUE (scope, scope_ref, period, data_mode)
);

CREATE TABLE channels (
	code VARCHAR(40) NOT NULL, 
	name VARCHAR(160) NOT NULL, 
	description TEXT NOT NULL, 
	platforms JSONB NOT NULL, 
	is_active BOOLEAN NOT NULL, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	deleted_at TIMESTAMP WITH TIME ZONE, 
	CONSTRAINT pk_channels PRIMARY KEY (id), 
	CONSTRAINT uq_channels_code UNIQUE (code)
);

CREATE TABLE projects (
	code VARCHAR(40) NOT NULL, 
	channel_id UUID NOT NULL, 
	batch_id UUID, 
	title VARCHAR(255) NOT NULL, 
	topic TEXT NOT NULL, 
	objective TEXT NOT NULL, 
	target_audience TEXT NOT NULL, 
	duration_sec INTEGER NOT NULL, 
	aspect_ratio VARCHAR(8) NOT NULL, 
	style VARCHAR(160) NOT NULL, 
	setting VARCHAR(255) NOT NULL, 
	cta VARCHAR(255) NOT NULL, 
	character_ids JSONB NOT NULL, 
	scene_lock_ids JSONB NOT NULL, 
	voice_profile_id UUID, 
	budget_limit NUMERIC(16, 2) NOT NULL, 
	automation_level VARCHAR(12) NOT NULL, 
	video_provider_code VARCHAR(60) NOT NULL, 
	status VARCHAR(32) NOT NULL, 
	resume_status VARCHAR(32), 
	progress INTEGER NOT NULL, 
	owner_id UUID, 
	created_by UUID, 
	deadline TIMESTAMP WITH TIME ZONE, 
	priority VARCHAR(8) NOT NULL, 
	idempotency_key VARCHAR(100), 
	timeline JSONB NOT NULL, 
	last_error TEXT, 
	retry_count INTEGER NOT NULL, 
	approved_by UUID, 
	approved_at TIMESTAMP WITH TIME ZONE, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	deleted_at TIMESTAMP WITH TIME ZONE, 
	data_mode VARCHAR(16) NOT NULL, 
	CONSTRAINT pk_projects PRIMARY KEY (id), 
	CONSTRAINT uq_projects_code UNIQUE (code), 
	CONSTRAINT uq_projects_idempotency_key UNIQUE (idempotency_key)
);

CREATE INDEX ix_projects_batch_id ON projects (batch_id);

CREATE INDEX ix_projects_owner_id ON projects (owner_id);

CREATE INDEX ix_projects_data_mode ON projects (data_mode);

CREATE INDEX ix_projects_channel_id ON projects (channel_id);

CREATE INDEX ix_projects_status ON projects (status);

CREATE INDEX ix_projects_mode_status ON projects (data_mode, status);

CREATE TABLE scenes (
	project_id UUID NOT NULL, 
	order_index INTEGER NOT NULL, 
	title VARCHAR(255) NOT NULL, 
	scene_type VARCHAR(60) NOT NULL, 
	duration_sec INTEGER NOT NULL, 
	action TEXT NOT NULL, 
	dialogue JSONB NOT NULL, 
	setting TEXT NOT NULL, 
	camera VARCHAR(255) NOT NULL, 
	lighting VARCHAR(255) NOT NULL, 
	sound VARCHAR(255) NOT NULL, 
	character_ids JSONB NOT NULL, 
	scene_lock_id UUID, 
	prompt_text TEXT NOT NULL, 
	prompt_parts JSONB NOT NULL, 
	negative_prompt TEXT NOT NULL, 
	prompt_version_id UUID, 
	current_version_no INTEGER NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	selected_asset_id UUID, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	data_mode VARCHAR(16) NOT NULL, 
	CONSTRAINT pk_scenes PRIMARY KEY (id), 
	CONSTRAINT scene_order UNIQUE (project_id, order_index)
);

CREATE INDEX ix_scenes_data_mode ON scenes (data_mode);

CREATE INDEX ix_scenes_project_id ON scenes (project_id);

CREATE TABLE voice_profiles (
	code VARCHAR(40) NOT NULL, 
	name VARCHAR(160) NOT NULL, 
	accent VARCHAR(60) NOT NULL, 
	gender VARCHAR(20) NOT NULL, 
	age_range VARCHAR(40) NOT NULL, 
	tone VARCHAR(160) NOT NULL, 
	speaking_rate VARCHAR(40) NOT NULL, 
	provider_code VARCHAR(60) NOT NULL, 
	provider_voice_id VARCHAR(120), 
	audio_reference_asset_id UUID, 
	consent_status VARCHAR(20) NOT NULL, 
	consent_document_asset_id UUID, 
	usage_rights TEXT NOT NULL, 
	rights_expires_at TIMESTAMP WITH TIME ZONE, 
	active_lock_id UUID, 
	status VARCHAR(20) NOT NULL, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	deleted_at TIMESTAMP WITH TIME ZONE, 
	data_mode VARCHAR(16) NOT NULL, 
	CONSTRAINT pk_voice_profiles PRIMARY KEY (id), 
	CONSTRAINT uq_voice_profiles_code UNIQUE (code)
);

CREATE INDEX ix_voice_profiles_data_mode ON voice_profiles (data_mode);

CREATE TABLE assets (
	asset_type VARCHAR(20) NOT NULL, 
	name VARCHAR(255) NOT NULL, 
	description TEXT NOT NULL, 
	storage_backend VARCHAR(10) NOT NULL, 
	storage_key VARCHAR(500) NOT NULL, 
	mime_type VARCHAR(100) NOT NULL, 
	size_bytes BIGINT NOT NULL, 
	checksum_sha256 VARCHAR(64) NOT NULL, 
	duration_sec FLOAT, 
	width INTEGER, 
	height INTEGER, 
	media_info JSONB NOT NULL, 
	tags JSONB NOT NULL, 
	usage_rights VARCHAR(30) NOT NULL, 
	rights_note TEXT NOT NULL, 
	rights_expires_at TIMESTAMP WITH TIME ZONE, 
	source VARCHAR(30) NOT NULL, 
	version_no INTEGER NOT NULL, 
	parent_asset_id UUID, 
	channel_id UUID, 
	project_id UUID, 
	scene_id UUID, 
	uploaded_by UUID, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	deleted_at TIMESTAMP WITH TIME ZONE, 
	data_mode VARCHAR(16) NOT NULL, 
	CONSTRAINT pk_assets PRIMARY KEY (id), 
	CONSTRAINT uq_assets_storage_key UNIQUE (storage_key)
);

CREATE INDEX ix_assets_scene_id ON assets (scene_id);

CREATE INDEX ix_assets_project_id ON assets (project_id);

CREATE INDEX ix_assets_channel_id ON assets (channel_id);

CREATE INDEX ix_assets_checksum_sha256 ON assets (checksum_sha256);

CREATE INDEX ix_assets_mode_type ON assets (data_mode, asset_type);

CREATE INDEX ix_assets_data_mode ON assets (data_mode);

CREATE TABLE agent_configs (
	code VARCHAR(10) NOT NULL, 
	name VARCHAR(80) NOT NULL, 
	role_description TEXT NOT NULL, 
	provider_code VARCHAR(60) NOT NULL, 
	model VARCHAR(80) NOT NULL, 
	is_enabled BOOLEAN NOT NULL, 
	allowed_actions JSONB NOT NULL, 
	prompt_template_code VARCHAR(80), 
	max_runs_per_day INTEGER NOT NULL, 
	max_cost_per_run NUMERIC(16, 2) NOT NULL, 
	max_tokens INTEGER NOT NULL, 
	timeout_sec INTEGER NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_agent_configs PRIMARY KEY (code)
);

CREATE TABLE role_permissions (
	role_id UUID NOT NULL, 
	permission_id UUID NOT NULL, 
	CONSTRAINT pk_role_permissions PRIMARY KEY (role_id, permission_id), 
	CONSTRAINT fk_role_permissions_role_id_roles FOREIGN KEY(role_id) REFERENCES roles (id) ON DELETE CASCADE, 
	CONSTRAINT fk_role_permissions_permission_id_permissions FOREIGN KEY(permission_id) REFERENCES permissions (id) ON DELETE CASCADE
);

CREATE TABLE users (
	email VARCHAR(255) NOT NULL, 
	full_name VARCHAR(160) NOT NULL, 
	password_hash VARCHAR(255) NOT NULL, 
	role_id UUID NOT NULL, 
	is_active BOOLEAN NOT NULL, 
	must_change_password BOOLEAN NOT NULL, 
	failed_login_count INTEGER NOT NULL, 
	locked_until TIMESTAMP WITH TIME ZONE, 
	last_login_at TIMESTAMP WITH TIME ZONE, 
	is_demo BOOLEAN NOT NULL, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	deleted_at TIMESTAMP WITH TIME ZONE, 
	CONSTRAINT pk_users PRIMARY KEY (id), 
	CONSTRAINT fk_users_role_id_roles FOREIGN KEY(role_id) REFERENCES roles (id)
);

CREATE INDEX ix_users_role_id ON users (role_id);

CREATE UNIQUE INDEX ix_users_email ON users (email);

CREATE TABLE workflow_events (
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	project_id UUID NOT NULL, 
	from_status VARCHAR(32), 
	to_status VARCHAR(32) NOT NULL, 
	actor_type VARCHAR(16) NOT NULL, 
	actor_ref VARCHAR(64), 
	note TEXT NOT NULL, 
	payload JSONB NOT NULL, 
	id UUID NOT NULL, 
	CONSTRAINT pk_workflow_events PRIMARY KEY (id), 
	CONSTRAINT fk_workflow_events_project_id_projects FOREIGN KEY(project_id) REFERENCES projects (id) ON DELETE CASCADE
);

CREATE INDEX ix_workflow_events_created_at ON workflow_events (created_at);

CREATE INDEX ix_workflow_events_project_id ON workflow_events (project_id);

CREATE TABLE characters (
	code VARCHAR(40) NOT NULL, 
	channel_id UUID, 
	name VARCHAR(160) NOT NULL, 
	description TEXT NOT NULL, 
	age_range VARCHAR(40) NOT NULL, 
	gender VARCHAR(20) NOT NULL, 
	appearance TEXT NOT NULL, 
	outfit TEXT NOT NULL, 
	expressions JSONB NOT NULL, 
	personality TEXT NOT NULL, 
	voice_profile_id UUID, 
	active_lock_id UUID, 
	consent_status VARCHAR(20) NOT NULL, 
	usage_rights TEXT NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	deleted_at TIMESTAMP WITH TIME ZONE, 
	data_mode VARCHAR(16) NOT NULL, 
	CONSTRAINT pk_characters PRIMARY KEY (id), 
	CONSTRAINT uq_characters_code UNIQUE (code), 
	CONSTRAINT fk_characters_channel_id_channels FOREIGN KEY(channel_id) REFERENCES channels (id) ON DELETE SET NULL, 
	CONSTRAINT fk_characters_voice_profile_id_voice_profiles FOREIGN KEY(voice_profile_id) REFERENCES voice_profiles (id) ON DELETE SET NULL
);

CREATE INDEX ix_characters_data_mode ON characters (data_mode);

CREATE INDEX ix_characters_channel_id ON characters (channel_id);

CREATE TABLE prompt_templates (
	code VARCHAR(80) NOT NULL, 
	name VARCHAR(160) NOT NULL, 
	agent_code VARCHAR(10) NOT NULL, 
	purpose TEXT NOT NULL, 
	channel_id UUID, 
	active_version_id UUID, 
	demo_active_version_id UUID, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_prompt_templates PRIMARY KEY (id), 
	CONSTRAINT uq_prompt_templates_code UNIQUE (code), 
	CONSTRAINT fk_prompt_templates_channel_id_channels FOREIGN KEY(channel_id) REFERENCES channels (id) ON DELETE SET NULL
);

CREATE INDEX ix_prompt_templates_agent_code ON prompt_templates (agent_code);

CREATE TABLE system_settings (
	key VARCHAR(80) NOT NULL, 
	value JSONB NOT NULL, 
	updated_by UUID, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_system_settings PRIMARY KEY (key), 
	CONSTRAINT fk_system_settings_updated_by_users FOREIGN KEY(updated_by) REFERENCES users (id)
);

CREATE TABLE notifications (
	user_id UUID, 
	level VARCHAR(10) NOT NULL, 
	category VARCHAR(30) NOT NULL, 
	title VARCHAR(200) NOT NULL, 
	message TEXT NOT NULL, 
	link VARCHAR(255), 
	read_at TIMESTAMP WITH TIME ZONE, 
	data_mode VARCHAR(16) NOT NULL, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_notifications PRIMARY KEY (id), 
	CONSTRAINT fk_notifications_user_id_users FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE INDEX ix_notifications_user_id ON notifications (user_id);

CREATE TABLE backups (
	file_name VARCHAR(255) NOT NULL, 
	size_bytes INTEGER NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	checksum VARCHAR(80), 
	created_by UUID, 
	note VARCHAR(255) NOT NULL, 
	restored_at TIMESTAMP WITH TIME ZONE, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_backups PRIMARY KEY (id), 
	CONSTRAINT fk_backups_created_by_users FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE TABLE brand_profiles (
	channel_id UUID NOT NULL, 
	slogan VARCHAR(255) NOT NULL, 
	brand_promise VARCHAR(255) NOT NULL, 
	big_idea VARCHAR(255) NOT NULL, 
	brand_voice JSONB NOT NULL, 
	audience TEXT NOT NULL, 
	content_pillars JSONB NOT NULL, 
	character_set JSONB NOT NULL, 
	voice_set JSONB NOT NULL, 
	scene_set JSONB NOT NULL, 
	cta_rules JSONB NOT NULL, 
	quality_rules JSONB NOT NULL, 
	publishing_rules JSONB NOT NULL, 
	forbidden_terms JSONB NOT NULL, 
	version_no INTEGER NOT NULL, 
	history JSONB NOT NULL, 
	updated_by UUID, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_brand_profiles PRIMARY KEY (id), 
	CONSTRAINT uq_brand_profiles_channel_id UNIQUE (channel_id), 
	CONSTRAINT fk_brand_profiles_channel_id_channels FOREIGN KEY(channel_id) REFERENCES channels (id) ON DELETE CASCADE, 
	CONSTRAINT fk_brand_profiles_updated_by_users FOREIGN KEY(updated_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE TABLE production_batches (
	code VARCHAR(40) NOT NULL, 
	channel_id UUID NOT NULL, 
	title VARCHAR(200) NOT NULL, 
	quantity INTEGER NOT NULL, 
	created_by UUID, 
	idempotency_key VARCHAR(100), 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	data_mode VARCHAR(16) NOT NULL, 
	CONSTRAINT pk_production_batches PRIMARY KEY (id), 
	CONSTRAINT uq_production_batches_code UNIQUE (code), 
	CONSTRAINT fk_production_batches_channel_id_channels FOREIGN KEY(channel_id) REFERENCES channels (id), 
	CONSTRAINT fk_production_batches_created_by_users FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL, 
	CONSTRAINT uq_production_batches_idempotency_key UNIQUE (idempotency_key)
);

CREATE INDEX ix_production_batches_data_mode ON production_batches (data_mode);

CREATE TABLE scripts (
	project_id UUID NOT NULL, 
	ideas JSONB NOT NULL, 
	selected_idea_index INTEGER, 
	current_version_id UUID, 
	status VARCHAR(20) NOT NULL, 
	approved_version_id UUID, 
	approved_by UUID, 
	approved_at TIMESTAMP WITH TIME ZONE, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	data_mode VARCHAR(16) NOT NULL, 
	CONSTRAINT pk_scripts PRIMARY KEY (id), 
	CONSTRAINT uq_scripts_project_id UNIQUE (project_id), 
	CONSTRAINT fk_scripts_project_id_projects FOREIGN KEY(project_id) REFERENCES projects (id) ON DELETE CASCADE, 
	CONSTRAINT fk_scripts_approved_by_users FOREIGN KEY(approved_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_scripts_data_mode ON scripts (data_mode);

CREATE TABLE scene_versions (
	scene_id UUID NOT NULL, 
	version_no INTEGER NOT NULL, 
	snapshot JSONB NOT NULL, 
	prompt_text TEXT NOT NULL, 
	negative_prompt TEXT NOT NULL, 
	change_note VARCHAR(255) NOT NULL, 
	created_by UUID, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_scene_versions PRIMARY KEY (id), 
	CONSTRAINT scene_version_no UNIQUE (scene_id, version_no), 
	CONSTRAINT fk_scene_versions_scene_id_scenes FOREIGN KEY(scene_id) REFERENCES scenes (id) ON DELETE CASCADE, 
	CONSTRAINT fk_scene_versions_created_by_users FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_scene_versions_scene_id ON scene_versions (scene_id);

CREATE TABLE character_references (
	character_id UUID NOT NULL, 
	ref_type VARCHAR(20) NOT NULL, 
	asset_id UUID NOT NULL, 
	version_no INTEGER NOT NULL, 
	note VARCHAR(255) NOT NULL, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_character_references PRIMARY KEY (id), 
	CONSTRAINT char_ref_version UNIQUE (character_id, ref_type, version_no), 
	CONSTRAINT fk_character_references_character_id_characters FOREIGN KEY(character_id) REFERENCES characters (id) ON DELETE CASCADE, 
	CONSTRAINT fk_character_references_asset_id_assets FOREIGN KEY(asset_id) REFERENCES assets (id)
);

CREATE INDEX ix_character_references_character_id ON character_references (character_id);

CREATE TABLE character_locks (
	character_id UUID NOT NULL, 
	version_no INTEGER NOT NULL, 
	lock_data JSONB NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	created_by UUID, 
	approved_by UUID, 
	approved_at TIMESTAMP WITH TIME ZONE, 
	retired_at TIMESTAMP WITH TIME ZONE, 
	change_note VARCHAR(255) NOT NULL, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_character_locks PRIMARY KEY (id), 
	CONSTRAINT char_lock_version UNIQUE (character_id, version_no), 
	CONSTRAINT fk_character_locks_character_id_characters FOREIGN KEY(character_id) REFERENCES characters (id) ON DELETE CASCADE, 
	CONSTRAINT fk_character_locks_created_by_users FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL, 
	CONSTRAINT fk_character_locks_approved_by_users FOREIGN KEY(approved_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_character_locks_character_id ON character_locks (character_id);

CREATE TABLE voice_locks (
	voice_profile_id UUID NOT NULL, 
	version_no INTEGER NOT NULL, 
	lock_data JSONB NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	created_by UUID, 
	approved_by UUID, 
	approved_at TIMESTAMP WITH TIME ZONE, 
	retired_at TIMESTAMP WITH TIME ZONE, 
	change_note VARCHAR(255) NOT NULL, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_voice_locks PRIMARY KEY (id), 
	CONSTRAINT voice_lock_version UNIQUE (voice_profile_id, version_no), 
	CONSTRAINT fk_voice_locks_voice_profile_id_voice_profiles FOREIGN KEY(voice_profile_id) REFERENCES voice_profiles (id) ON DELETE CASCADE, 
	CONSTRAINT fk_voice_locks_created_by_users FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL, 
	CONSTRAINT fk_voice_locks_approved_by_users FOREIGN KEY(approved_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_voice_locks_voice_profile_id ON voice_locks (voice_profile_id);

CREATE TABLE scene_locks (
	code VARCHAR(40) NOT NULL, 
	version_no INTEGER NOT NULL, 
	channel_id UUID, 
	name VARCHAR(160) NOT NULL, 
	lock_data JSONB NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	created_by UUID, 
	approved_by UUID, 
	approved_at TIMESTAMP WITH TIME ZONE, 
	retired_at TIMESTAMP WITH TIME ZONE, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	data_mode VARCHAR(16) NOT NULL, 
	CONSTRAINT pk_scene_locks PRIMARY KEY (id), 
	CONSTRAINT scene_lock_version UNIQUE (code, version_no), 
	CONSTRAINT fk_scene_locks_channel_id_channels FOREIGN KEY(channel_id) REFERENCES channels (id) ON DELETE SET NULL, 
	CONSTRAINT fk_scene_locks_created_by_users FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL, 
	CONSTRAINT fk_scene_locks_approved_by_users FOREIGN KEY(approved_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_scene_locks_code ON scene_locks (code);

CREATE INDEX ix_scene_locks_data_mode ON scene_locks (data_mode);

CREATE TABLE prompt_versions (
	template_id UUID NOT NULL, 
	version_no INTEGER NOT NULL, 
	content TEXT NOT NULL, 
	negative_prompt TEXT NOT NULL, 
	rules JSONB NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	data_mode VARCHAR(16) NOT NULL, 
	change_note VARCHAR(255) NOT NULL, 
	source_lesson_id UUID, 
	created_by UUID, 
	approved_by UUID, 
	approved_at TIMESTAMP WITH TIME ZONE, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_prompt_versions PRIMARY KEY (id), 
	CONSTRAINT prompt_version_no UNIQUE (template_id, version_no), 
	CONSTRAINT fk_prompt_versions_template_id_prompt_templates FOREIGN KEY(template_id) REFERENCES prompt_templates (id) ON DELETE CASCADE, 
	CONSTRAINT fk_prompt_versions_created_by_users FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL, 
	CONSTRAINT fk_prompt_versions_approved_by_users FOREIGN KEY(approved_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_prompt_versions_template_id ON prompt_versions (template_id);

CREATE TABLE generation_jobs (
	project_id UUID NOT NULL, 
	scene_id UUID NOT NULL, 
	scene_version_no INTEGER NOT NULL, 
	provider_code VARCHAR(60) NOT NULL, 
	status VARCHAR(24) NOT NULL, 
	attempt_no INTEGER NOT NULL, 
	max_retries INTEGER NOT NULL, 
	provider_job_id VARCHAR(160), 
	prompt_snapshot JSONB NOT NULL, 
	estimated_cost NUMERIC(16, 2) NOT NULL, 
	actual_cost NUMERIC(16, 2) NOT NULL, 
	result_asset_id UUID, 
	error_code VARCHAR(60), 
	error_message TEXT, 
	idempotency_key VARCHAR(160) NOT NULL, 
	celery_task_id VARCHAR(160), 
	requested_by UUID, 
	started_at TIMESTAMP WITH TIME ZONE, 
	finished_at TIMESTAMP WITH TIME ZONE, 
	log JSONB NOT NULL, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	data_mode VARCHAR(16) NOT NULL, 
	CONSTRAINT pk_generation_jobs PRIMARY KEY (id), 
	CONSTRAINT fk_generation_jobs_project_id_projects FOREIGN KEY(project_id) REFERENCES projects (id) ON DELETE CASCADE, 
	CONSTRAINT fk_generation_jobs_scene_id_scenes FOREIGN KEY(scene_id) REFERENCES scenes (id) ON DELETE CASCADE, 
	CONSTRAINT fk_generation_jobs_result_asset_id_assets FOREIGN KEY(result_asset_id) REFERENCES assets (id) ON DELETE SET NULL, 
	CONSTRAINT uq_generation_jobs_idempotency_key UNIQUE (idempotency_key), 
	CONSTRAINT fk_generation_jobs_requested_by_users FOREIGN KEY(requested_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_generation_jobs_scene_id ON generation_jobs (scene_id);

CREATE INDEX ix_generation_jobs_project_id ON generation_jobs (project_id);

CREATE INDEX ix_generation_jobs_data_mode ON generation_jobs (data_mode);

CREATE INDEX ix_generation_jobs_status ON generation_jobs (status);

CREATE INDEX ix_generation_jobs_mode_status ON generation_jobs (data_mode, status);

CREATE TABLE render_jobs (
	project_id UUID NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	timeline JSONB NOT NULL, 
	attempt_no INTEGER NOT NULL, 
	max_retries INTEGER NOT NULL, 
	idempotency_key VARCHAR(160) NOT NULL, 
	celery_task_id VARCHAR(160), 
	error_message TEXT, 
	log JSONB NOT NULL, 
	requested_by UUID, 
	started_at TIMESTAMP WITH TIME ZONE, 
	finished_at TIMESTAMP WITH TIME ZONE, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	data_mode VARCHAR(16) NOT NULL, 
	CONSTRAINT pk_render_jobs PRIMARY KEY (id), 
	CONSTRAINT fk_render_jobs_project_id_projects FOREIGN KEY(project_id) REFERENCES projects (id) ON DELETE CASCADE, 
	CONSTRAINT uq_render_jobs_idempotency_key UNIQUE (idempotency_key), 
	CONSTRAINT fk_render_jobs_requested_by_users FOREIGN KEY(requested_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_render_jobs_data_mode ON render_jobs (data_mode);

CREATE INDEX ix_render_jobs_project_id ON render_jobs (project_id);

CREATE INDEX ix_render_jobs_status ON render_jobs (status);

CREATE TABLE renders (
	project_id UUID NOT NULL, 
	render_job_id UUID NOT NULL, 
	version_no INTEGER NOT NULL, 
	video_asset_id UUID NOT NULL, 
	thumbnail_asset_id UUID, 
	subtitle_asset_id UUID, 
	duration_sec FLOAT NOT NULL, 
	width INTEGER NOT NULL, 
	height INTEGER NOT NULL, 
	size_bytes BIGINT NOT NULL, 
	probe JSONB NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	notes TEXT NOT NULL, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	data_mode VARCHAR(16) NOT NULL, 
	CONSTRAINT pk_renders PRIMARY KEY (id), 
	CONSTRAINT render_version_no UNIQUE (project_id, version_no), 
	CONSTRAINT fk_renders_project_id_projects FOREIGN KEY(project_id) REFERENCES projects (id) ON DELETE CASCADE, 
	CONSTRAINT fk_renders_render_job_id_render_jobs FOREIGN KEY(render_job_id) REFERENCES render_jobs (id) ON DELETE CASCADE, 
	CONSTRAINT fk_renders_video_asset_id_assets FOREIGN KEY(video_asset_id) REFERENCES assets (id), 
	CONSTRAINT fk_renders_thumbnail_asset_id_assets FOREIGN KEY(thumbnail_asset_id) REFERENCES assets (id), 
	CONSTRAINT fk_renders_subtitle_asset_id_assets FOREIGN KEY(subtitle_asset_id) REFERENCES assets (id)
);

CREATE INDEX ix_renders_data_mode ON renders (data_mode);

CREATE INDEX ix_renders_project_id ON renders (project_id);

CREATE TABLE agent_executions (
	agent_code VARCHAR(10) NOT NULL, 
	action VARCHAR(60) NOT NULL, 
	model VARCHAR(80) NOT NULL, 
	provider_code VARCHAR(60) NOT NULL, 
	prompt_version_id UUID, 
	prompt_version_label VARCHAR(80), 
	project_id UUID, 
	input_ref JSONB NOT NULL, 
	output_ref JSONB NOT NULL, 
	input_tokens INTEGER NOT NULL, 
	output_tokens INTEGER NOT NULL, 
	cost NUMERIC(16, 2) NOT NULL, 
	is_simulated BOOLEAN NOT NULL, 
	latency_ms INTEGER NOT NULL, 
	status VARCHAR(16) NOT NULL, 
	error TEXT, 
	triggered_by VARCHAR(64), 
	started_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	finished_at TIMESTAMP WITH TIME ZONE, 
	id UUID NOT NULL, 
	data_mode VARCHAR(16) NOT NULL, 
	CONSTRAINT pk_agent_executions PRIMARY KEY (id), 
	CONSTRAINT fk_agent_executions_agent_code_agent_configs FOREIGN KEY(agent_code) REFERENCES agent_configs (code), 
	CONSTRAINT fk_agent_executions_prompt_version_id_prompt_versions FOREIGN KEY(prompt_version_id) REFERENCES prompt_versions (id) ON DELETE SET NULL, 
	CONSTRAINT fk_agent_executions_project_id_projects FOREIGN KEY(project_id) REFERENCES projects (id) ON DELETE SET NULL
);

CREATE INDEX ix_agent_executions_data_mode ON agent_executions (data_mode);

CREATE INDEX ix_agent_exec_agent_time ON agent_executions (agent_code, started_at);

CREATE INDEX ix_agent_executions_agent_code ON agent_executions (agent_code);

CREATE INDEX ix_agent_executions_project_id ON agent_executions (project_id);

CREATE TABLE cost_records (
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	project_id UUID, 
	channel_id UUID, 
	scene_id UUID, 
	generation_job_id UUID, 
	agent_execution_id UUID, 
	category VARCHAR(20) NOT NULL, 
	provider_code VARCHAR(60) NOT NULL, 
	quantity NUMERIC(16, 4) NOT NULL, 
	unit VARCHAR(30) NOT NULL, 
	amount NUMERIC(16, 2) NOT NULL, 
	is_simulated BOOLEAN NOT NULL, 
	description VARCHAR(255) NOT NULL, 
	id UUID NOT NULL, 
	data_mode VARCHAR(16) NOT NULL, 
	CONSTRAINT pk_cost_records PRIMARY KEY (id), 
	CONSTRAINT fk_cost_records_project_id_projects FOREIGN KEY(project_id) REFERENCES projects (id) ON DELETE SET NULL, 
	CONSTRAINT fk_cost_records_channel_id_channels FOREIGN KEY(channel_id) REFERENCES channels (id) ON DELETE SET NULL, 
	CONSTRAINT fk_cost_records_scene_id_scenes FOREIGN KEY(scene_id) REFERENCES scenes (id) ON DELETE SET NULL, 
	CONSTRAINT fk_cost_records_generation_job_id_generation_jobs FOREIGN KEY(generation_job_id) REFERENCES generation_jobs (id) ON DELETE SET NULL, 
	CONSTRAINT fk_cost_records_agent_execution_id_agent_executions FOREIGN KEY(agent_execution_id) REFERENCES agent_executions (id) ON DELETE SET NULL
);

CREATE INDEX ix_cost_records_created_at ON cost_records (created_at);

CREATE INDEX ix_cost_records_data_mode ON cost_records (data_mode);

CREATE INDEX ix_cost_records_project_id ON cost_records (project_id);

CREATE INDEX ix_cost_records_channel_id ON cost_records (channel_id);

CREATE INDEX ix_cost_records_period ON cost_records (data_mode, created_at);

CREATE TABLE script_versions (
	script_id UUID NOT NULL, 
	version_no INTEGER NOT NULL, 
	title VARCHAR(255) NOT NULL, 
	hook TEXT NOT NULL, 
	body TEXT NOT NULL, 
	cta VARCHAR(255) NOT NULL, 
	scenes JSONB NOT NULL, 
	source VARCHAR(10) NOT NULL, 
	change_note VARCHAR(255) NOT NULL, 
	created_by UUID, 
	agent_execution_id UUID, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_script_versions PRIMARY KEY (id), 
	CONSTRAINT script_version_no UNIQUE (script_id, version_no), 
	CONSTRAINT fk_script_versions_script_id_scripts FOREIGN KEY(script_id) REFERENCES scripts (id) ON DELETE CASCADE, 
	CONSTRAINT fk_script_versions_created_by_users FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL, 
	CONSTRAINT fk_script_versions_agent_execution_id_agent_executions FOREIGN KEY(agent_execution_id) REFERENCES agent_executions (id) ON DELETE SET NULL
);

CREATE INDEX ix_script_versions_script_id ON script_versions (script_id);

CREATE TABLE qc_reviews (
	project_id UUID NOT NULL, 
	render_id UUID, 
	scene_id UUID, 
	review_type VARCHAR(10) NOT NULL, 
	reviewer_type VARCHAR(10) NOT NULL, 
	reviewer_id UUID, 
	scores JSONB NOT NULL, 
	total_score FLOAT NOT NULL, 
	pending_manual JSONB NOT NULL, 
	automated_checks JSONB NOT NULL, 
	has_critical BOOLEAN NOT NULL, 
	result VARCHAR(20) NOT NULL, 
	notes TEXT NOT NULL, 
	agent_execution_id UUID, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	data_mode VARCHAR(16) NOT NULL, 
	CONSTRAINT pk_qc_reviews PRIMARY KEY (id), 
	CONSTRAINT fk_qc_reviews_project_id_projects FOREIGN KEY(project_id) REFERENCES projects (id) ON DELETE CASCADE, 
	CONSTRAINT fk_qc_reviews_render_id_renders FOREIGN KEY(render_id) REFERENCES renders (id) ON DELETE SET NULL, 
	CONSTRAINT fk_qc_reviews_scene_id_scenes FOREIGN KEY(scene_id) REFERENCES scenes (id) ON DELETE SET NULL, 
	CONSTRAINT fk_qc_reviews_reviewer_id_users FOREIGN KEY(reviewer_id) REFERENCES users (id) ON DELETE SET NULL, 
	CONSTRAINT fk_qc_reviews_agent_execution_id_agent_executions FOREIGN KEY(agent_execution_id) REFERENCES agent_executions (id) ON DELETE SET NULL
);

CREATE INDEX ix_qc_reviews_data_mode ON qc_reviews (data_mode);

CREATE INDEX ix_qc_reviews_project_id ON qc_reviews (project_id);

CREATE TABLE publications (
	project_id UUID NOT NULL, 
	render_id UUID, 
	channel_id UUID NOT NULL, 
	platform VARCHAR(20) NOT NULL, 
	caption TEXT NOT NULL, 
	hashtags JSONB NOT NULL, 
	scheduled_at TIMESTAMP WITH TIME ZONE, 
	published_at TIMESTAMP WITH TIME ZONE, 
	post_url VARCHAR(500), 
	publish_mode VARCHAR(10) NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	export_asset_id UUID, 
	error_message TEXT, 
	created_by UUID, 
	published_by UUID, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	data_mode VARCHAR(16) NOT NULL, 
	CONSTRAINT pk_publications PRIMARY KEY (id), 
	CONSTRAINT fk_publications_project_id_projects FOREIGN KEY(project_id) REFERENCES projects (id) ON DELETE CASCADE, 
	CONSTRAINT fk_publications_render_id_renders FOREIGN KEY(render_id) REFERENCES renders (id) ON DELETE SET NULL, 
	CONSTRAINT fk_publications_channel_id_channels FOREIGN KEY(channel_id) REFERENCES channels (id), 
	CONSTRAINT fk_publications_export_asset_id_assets FOREIGN KEY(export_asset_id) REFERENCES assets (id) ON DELETE SET NULL, 
	CONSTRAINT fk_publications_created_by_users FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL, 
	CONSTRAINT fk_publications_published_by_users FOREIGN KEY(published_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_publications_channel_id ON publications (channel_id);

CREATE INDEX ix_publications_status ON publications (status);

CREATE INDEX ix_publications_data_mode ON publications (data_mode);

CREATE INDEX ix_publications_scheduled_at ON publications (scheduled_at);

CREATE INDEX ix_publications_project_id ON publications (project_id);

CREATE TABLE qc_findings (
	qc_review_id UUID NOT NULL, 
	project_id UUID NOT NULL, 
	scene_id UUID, 
	criterion VARCHAR(30) NOT NULL, 
	severity VARCHAR(10) NOT NULL, 
	description TEXT NOT NULL, 
	evidence JSONB NOT NULL, 
	status VARCHAR(10) NOT NULL, 
	resolved_by UUID, 
	resolved_at TIMESTAMP WITH TIME ZONE, 
	resolution_note TEXT NOT NULL, 
	feedback_case_id UUID, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_qc_findings PRIMARY KEY (id), 
	CONSTRAINT fk_qc_findings_qc_review_id_qc_reviews FOREIGN KEY(qc_review_id) REFERENCES qc_reviews (id) ON DELETE CASCADE, 
	CONSTRAINT fk_qc_findings_project_id_projects FOREIGN KEY(project_id) REFERENCES projects (id) ON DELETE CASCADE, 
	CONSTRAINT fk_qc_findings_scene_id_scenes FOREIGN KEY(scene_id) REFERENCES scenes (id) ON DELETE SET NULL, 
	CONSTRAINT fk_qc_findings_resolved_by_users FOREIGN KEY(resolved_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_qc_findings_qc_review_id ON qc_findings (qc_review_id);

CREATE INDEX ix_qc_findings_project_id ON qc_findings (project_id);

CREATE TABLE approvals (
	project_id UUID NOT NULL, 
	render_id UUID, 
	qc_review_id UUID, 
	approver_id UUID NOT NULL, 
	decision VARCHAR(10) NOT NULL, 
	comment TEXT NOT NULL, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	data_mode VARCHAR(16) NOT NULL, 
	CONSTRAINT pk_approvals PRIMARY KEY (id), 
	CONSTRAINT fk_approvals_project_id_projects FOREIGN KEY(project_id) REFERENCES projects (id) ON DELETE CASCADE, 
	CONSTRAINT fk_approvals_render_id_renders FOREIGN KEY(render_id) REFERENCES renders (id) ON DELETE SET NULL, 
	CONSTRAINT fk_approvals_qc_review_id_qc_reviews FOREIGN KEY(qc_review_id) REFERENCES qc_reviews (id) ON DELETE SET NULL, 
	CONSTRAINT fk_approvals_approver_id_users FOREIGN KEY(approver_id) REFERENCES users (id)
);

CREATE INDEX ix_approvals_project_id ON approvals (project_id);

CREATE INDEX ix_approvals_data_mode ON approvals (data_mode);

CREATE TABLE analytics_snapshots (
	publication_id UUID NOT NULL, 
	project_id UUID NOT NULL, 
	captured_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	views INTEGER NOT NULL, 
	likes INTEGER NOT NULL, 
	comments INTEGER NOT NULL, 
	shares INTEGER NOT NULL, 
	saves INTEGER NOT NULL, 
	retention_rate FLOAT, 
	avg_watch_sec FLOAT, 
	conversions INTEGER, 
	source VARCHAR(10) NOT NULL, 
	entered_by UUID, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	data_mode VARCHAR(16) NOT NULL, 
	CONSTRAINT pk_analytics_snapshots PRIMARY KEY (id), 
	CONSTRAINT fk_analytics_snapshots_publication_id_publications FOREIGN KEY(publication_id) REFERENCES publications (id) ON DELETE CASCADE, 
	CONSTRAINT fk_analytics_snapshots_project_id_projects FOREIGN KEY(project_id) REFERENCES projects (id) ON DELETE CASCADE, 
	CONSTRAINT fk_analytics_snapshots_entered_by_users FOREIGN KEY(entered_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_analytics_snapshots_project_id ON analytics_snapshots (project_id);

CREATE INDEX ix_analytics_snapshots_publication_id ON analytics_snapshots (publication_id);

CREATE INDEX ix_analytics_snapshots_captured_at ON analytics_snapshots (captured_at);

CREATE INDEX ix_analytics_snapshots_data_mode ON analytics_snapshots (data_mode);

CREATE TABLE feedback_cases (
	code VARCHAR(40) NOT NULL, 
	project_id UUID, 
	scene_id UUID, 
	channel_id UUID, 
	character_id UUID, 
	provider_code VARCHAR(60), 
	qc_finding_id UUID, 
	source VARCHAR(20) NOT NULL, 
	category VARCHAR(40) NOT NULL, 
	title VARCHAR(255) NOT NULL, 
	description TEXT NOT NULL, 
	evidence JSONB NOT NULL, 
	evidence_class VARCHAR(12) NOT NULL, 
	priority VARCHAR(4), 
	status VARCHAR(20) NOT NULL, 
	owner_id UUID, 
	deadline TIMESTAMP WITH TIME ZONE, 
	kpi_name VARCHAR(120), 
	kpi_before FLOAT, 
	kpi_after FLOAT, 
	kpi_target FLOAT, 
	approver_id UUID, 
	reported_by UUID, 
	reopen_count INTEGER NOT NULL, 
	standardization_note TEXT NOT NULL, 
	closed_at TIMESTAMP WITH TIME ZONE, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	data_mode VARCHAR(16) NOT NULL, 
	CONSTRAINT pk_feedback_cases PRIMARY KEY (id), 
	CONSTRAINT uq_feedback_cases_code UNIQUE (code), 
	CONSTRAINT fk_feedback_cases_project_id_projects FOREIGN KEY(project_id) REFERENCES projects (id) ON DELETE SET NULL, 
	CONSTRAINT fk_feedback_cases_scene_id_scenes FOREIGN KEY(scene_id) REFERENCES scenes (id) ON DELETE SET NULL, 
	CONSTRAINT fk_feedback_cases_channel_id_channels FOREIGN KEY(channel_id) REFERENCES channels (id) ON DELETE SET NULL, 
	CONSTRAINT fk_feedback_cases_character_id_characters FOREIGN KEY(character_id) REFERENCES characters (id) ON DELETE SET NULL, 
	CONSTRAINT fk_feedback_cases_qc_finding_id_qc_findings FOREIGN KEY(qc_finding_id) REFERENCES qc_findings (id) ON DELETE SET NULL, 
	CONSTRAINT fk_feedback_cases_owner_id_users FOREIGN KEY(owner_id) REFERENCES users (id) ON DELETE SET NULL, 
	CONSTRAINT fk_feedback_cases_approver_id_users FOREIGN KEY(approver_id) REFERENCES users (id) ON DELETE SET NULL, 
	CONSTRAINT fk_feedback_cases_reported_by_users FOREIGN KEY(reported_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_feedback_cases_project_id ON feedback_cases (project_id);

CREATE INDEX ix_feedback_mode_status ON feedback_cases (data_mode, status);

CREATE INDEX ix_feedback_cases_data_mode ON feedback_cases (data_mode);

CREATE INDEX ix_feedback_cases_status ON feedback_cases (status);

CREATE TABLE feedback_events (
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	feedback_case_id UUID NOT NULL, 
	step VARCHAR(20) NOT NULL, 
	from_status VARCHAR(20), 
	to_status VARCHAR(20) NOT NULL, 
	actor_type VARCHAR(10) NOT NULL, 
	actor_ref VARCHAR(64), 
	note TEXT NOT NULL, 
	id UUID NOT NULL, 
	CONSTRAINT pk_feedback_events PRIMARY KEY (id), 
	CONSTRAINT fk_feedback_events_feedback_case_id_feedback_cases FOREIGN KEY(feedback_case_id) REFERENCES feedback_cases (id) ON DELETE CASCADE
);

CREATE INDEX ix_feedback_events_feedback_case_id ON feedback_events (feedback_case_id);

CREATE TABLE root_cause_analyses (
	feedback_case_id UUID NOT NULL, 
	whys JSONB NOT NULL, 
	root_cause TEXT NOT NULL, 
	cause_category VARCHAR(40) NOT NULL, 
	evidence_class VARCHAR(12) NOT NULL, 
	confidence_pct INTEGER NOT NULL, 
	created_by_type VARCHAR(10) NOT NULL, 
	created_by UUID, 
	is_current BOOLEAN NOT NULL, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_root_cause_analyses PRIMARY KEY (id), 
	CONSTRAINT fk_root_cause_analyses_feedback_case_id_feedback_cases FOREIGN KEY(feedback_case_id) REFERENCES feedback_cases (id) ON DELETE CASCADE, 
	CONSTRAINT fk_root_cause_analyses_created_by_users FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_root_cause_analyses_feedback_case_id ON root_cause_analyses (feedback_case_id);

CREATE TABLE capa_actions (
	feedback_case_id UUID NOT NULL, 
	action_type VARCHAR(12) NOT NULL, 
	description TEXT NOT NULL, 
	owner_id UUID, 
	deadline TIMESTAMP WITH TIME ZONE, 
	status VARCHAR(12) NOT NULL, 
	approved_by UUID, 
	approved_at TIMESTAMP WITH TIME ZONE, 
	completed_at TIMESTAMP WITH TIME ZONE, 
	completion_evidence JSONB NOT NULL, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_capa_actions PRIMARY KEY (id), 
	CONSTRAINT fk_capa_actions_feedback_case_id_feedback_cases FOREIGN KEY(feedback_case_id) REFERENCES feedback_cases (id) ON DELETE CASCADE, 
	CONSTRAINT fk_capa_actions_owner_id_users FOREIGN KEY(owner_id) REFERENCES users (id) ON DELETE SET NULL, 
	CONSTRAINT fk_capa_actions_approved_by_users FOREIGN KEY(approved_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_capa_actions_feedback_case_id ON capa_actions (feedback_case_id);

CREATE TABLE verification_results (
	feedback_case_id UUID NOT NULL, 
	method TEXT NOT NULL, 
	kpi_before FLOAT, 
	kpi_after FLOAT, 
	passed BOOLEAN NOT NULL, 
	evidence JSONB NOT NULL, 
	notes TEXT NOT NULL, 
	verified_by UUID, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_verification_results PRIMARY KEY (id), 
	CONSTRAINT fk_verification_results_feedback_case_id_feedback_cases FOREIGN KEY(feedback_case_id) REFERENCES feedback_cases (id) ON DELETE CASCADE, 
	CONSTRAINT fk_verification_results_verified_by_users FOREIGN KEY(verified_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_verification_results_feedback_case_id ON verification_results (feedback_case_id);

CREATE TABLE lessons_learned (
	code VARCHAR(40) NOT NULL, 
	feedback_case_id UUID, 
	lesson_type VARCHAR(30) NOT NULL, 
	title VARCHAR(255) NOT NULL, 
	lesson TEXT NOT NULL, 
	root_cause TEXT NOT NULL, 
	capa_summary TEXT NOT NULL, 
	verification_summary TEXT NOT NULL, 
	channel_id UUID, 
	character_id UUID, 
	error_category VARCHAR(40), 
	provider_code VARCHAR(60), 
	prompt_example TEXT NOT NULL, 
	proposed_change JSONB NOT NULL, 
	tags JSONB NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	version_no INTEGER NOT NULL, 
	history JSONB NOT NULL, 
	created_by UUID, 
	approved_by UUID, 
	approved_at TIMESTAMP WITH TIME ZONE, 
	applied_at TIMESTAMP WITH TIME ZONE, 
	applied_prompt_version_id UUID, 
	previous_prompt_version_id UUID, 
	rolled_back_at TIMESTAMP WITH TIME ZONE, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	data_mode VARCHAR(16) NOT NULL, 
	CONSTRAINT pk_lessons_learned PRIMARY KEY (id), 
	CONSTRAINT uq_lessons_learned_code UNIQUE (code), 
	CONSTRAINT fk_lessons_learned_feedback_case_id_feedback_cases FOREIGN KEY(feedback_case_id) REFERENCES feedback_cases (id) ON DELETE SET NULL, 
	CONSTRAINT fk_lessons_learned_channel_id_channels FOREIGN KEY(channel_id) REFERENCES channels (id) ON DELETE SET NULL, 
	CONSTRAINT fk_lessons_learned_character_id_characters FOREIGN KEY(character_id) REFERENCES characters (id) ON DELETE SET NULL, 
	CONSTRAINT fk_lessons_learned_created_by_users FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL, 
	CONSTRAINT fk_lessons_learned_approved_by_users FOREIGN KEY(approved_by) REFERENCES users (id) ON DELETE SET NULL, 
	CONSTRAINT fk_lessons_learned_applied_prompt_version_id_prompt_versions FOREIGN KEY(applied_prompt_version_id) REFERENCES prompt_versions (id) ON DELETE SET NULL, 
	CONSTRAINT fk_lessons_learned_previous_prompt_version_id_prompt_versions FOREIGN KEY(previous_prompt_version_id) REFERENCES prompt_versions (id) ON DELETE SET NULL
);

CREATE INDEX ix_lessons_learned_character_id ON lessons_learned (character_id);

CREATE INDEX ix_lessons_learned_error_category ON lessons_learned (error_category);

CREATE INDEX ix_lessons_learned_status ON lessons_learned (status);

CREATE INDEX ix_lessons_learned_data_mode ON lessons_learned (data_mode);

CREATE INDEX ix_lessons_learned_channel_id ON lessons_learned (channel_id);

CREATE INDEX ix_lessons_learned_provider_code ON lessons_learned (provider_code);

ALTER TABLE prompt_versions ADD CONSTRAINT fk_prompt_versions_source_lesson_id_lessons_learned FOREIGN KEY(source_lesson_id) REFERENCES lessons_learned (id) ON DELETE SET NULL;

ALTER TABLE assets ADD CONSTRAINT fk_assets_scene_id_scenes FOREIGN KEY(scene_id) REFERENCES scenes (id) ON DELETE SET NULL;

ALTER TABLE scenes ADD CONSTRAINT fk_scenes_scene_lock_id_scene_locks FOREIGN KEY(scene_lock_id) REFERENCES scene_locks (id) ON DELETE SET NULL;

ALTER TABLE assets ADD CONSTRAINT fk_assets_uploaded_by_users FOREIGN KEY(uploaded_by) REFERENCES users (id) ON DELETE SET NULL;

ALTER TABLE scenes ADD CONSTRAINT fk_scenes_prompt_version_id_prompt_versions FOREIGN KEY(prompt_version_id) REFERENCES prompt_versions (id) ON DELETE SET NULL;

ALTER TABLE voice_profiles ADD CONSTRAINT fk_voice_profiles_consent_document_asset_id_assets FOREIGN KEY(consent_document_asset_id) REFERENCES assets (id) ON DELETE SET NULL;

ALTER TABLE scripts ADD CONSTRAINT fk_scripts_current_version_id_script_versions FOREIGN KEY(current_version_id) REFERENCES script_versions (id) ON DELETE SET NULL;

ALTER TABLE characters ADD CONSTRAINT fk_characters_active_lock_id_character_locks FOREIGN KEY(active_lock_id) REFERENCES character_locks (id) ON DELETE SET NULL;

ALTER TABLE scenes ADD CONSTRAINT fk_scenes_selected_asset_id_assets FOREIGN KEY(selected_asset_id) REFERENCES assets (id) ON DELETE SET NULL;

ALTER TABLE voice_profiles ADD CONSTRAINT fk_voice_profiles_active_lock_id_voice_locks FOREIGN KEY(active_lock_id) REFERENCES voice_locks (id) ON DELETE SET NULL;

ALTER TABLE projects ADD CONSTRAINT fk_projects_channel_id_channels FOREIGN KEY(channel_id) REFERENCES channels (id);

ALTER TABLE scripts ADD CONSTRAINT fk_scripts_approved_version_id_script_versions FOREIGN KEY(approved_version_id) REFERENCES script_versions (id) ON DELETE SET NULL;

ALTER TABLE prompt_templates ADD CONSTRAINT fk_prompt_templates_active_version_id_prompt_versions FOREIGN KEY(active_version_id) REFERENCES prompt_versions (id) ON DELETE SET NULL;

ALTER TABLE projects ADD CONSTRAINT fk_projects_batch_id_production_batches FOREIGN KEY(batch_id) REFERENCES production_batches (id) ON DELETE SET NULL;

ALTER TABLE prompt_templates ADD CONSTRAINT fk_prompt_templates_demo_active_version_id_prompt_versions FOREIGN KEY(demo_active_version_id) REFERENCES prompt_versions (id) ON DELETE SET NULL;

ALTER TABLE projects ADD CONSTRAINT fk_projects_voice_profile_id_voice_profiles FOREIGN KEY(voice_profile_id) REFERENCES voice_profiles (id) ON DELETE SET NULL;

ALTER TABLE qc_findings ADD CONSTRAINT fk_qc_findings_feedback_case_id_feedback_cases FOREIGN KEY(feedback_case_id) REFERENCES feedback_cases (id) ON DELETE SET NULL;

ALTER TABLE projects ADD CONSTRAINT fk_projects_owner_id_users FOREIGN KEY(owner_id) REFERENCES users (id) ON DELETE SET NULL;

ALTER TABLE assets ADD CONSTRAINT fk_assets_parent_asset_id_assets FOREIGN KEY(parent_asset_id) REFERENCES assets (id) ON DELETE SET NULL;

ALTER TABLE projects ADD CONSTRAINT fk_projects_created_by_users FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL;

ALTER TABLE assets ADD CONSTRAINT fk_assets_channel_id_channels FOREIGN KEY(channel_id) REFERENCES channels (id) ON DELETE SET NULL;

ALTER TABLE voice_profiles ADD CONSTRAINT fk_voice_profiles_audio_reference_asset_id_assets FOREIGN KEY(audio_reference_asset_id) REFERENCES assets (id) ON DELETE SET NULL;

ALTER TABLE projects ADD CONSTRAINT fk_projects_approved_by_users FOREIGN KEY(approved_by) REFERENCES users (id) ON DELETE SET NULL;

ALTER TABLE assets ADD CONSTRAINT fk_assets_project_id_projects FOREIGN KEY(project_id) REFERENCES projects (id) ON DELETE SET NULL;

ALTER TABLE scenes ADD CONSTRAINT fk_scenes_project_id_projects FOREIGN KEY(project_id) REFERENCES projects (id) ON DELETE CASCADE;
