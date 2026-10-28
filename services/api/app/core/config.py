"""Cấu hình ứng dụng — đọc từ biến môi trường (xem .env.example)."""
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Ánh Ngân AI Video Studio"
    app_version: str = "2.0.0"
    environment: str = Field(default="development", description="development | test | production")

    database_url: str = "postgresql+psycopg://anngan:anngan@localhost:5432/anngan_studio"
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str | None = None
    celery_result_backend: str | None = None
    celery_task_always_eager: bool = False

    # Bảo mật
    secret_key: str = Field(default="CHANGE_ME_DEV_ONLY_SECRET_KEY_32_CHARS_MIN")
    encryption_key: str | None = Field(default=None, description="Fernet key cho API key nhà cung cấp")
    access_token_expire_minutes: int = 60 * 8
    cookie_secure: bool = False
    cors_origins: str = "http://localhost:3000"
    login_rate_limit_per_minute: int = 10
    api_rate_limit_per_minute: int = 600

    # Lưu trữ
    storage_backend: str = "local"  # local | s3
    storage_local_root: str = str(Path(__file__).resolve().parents[4] / "var" / "storage")
    s3_endpoint_url: str | None = None
    s3_bucket: str = "anngan-media"
    s3_access_key: str | None = None
    s3_secret_key: str | None = None
    s3_region: str = "us-east-1"
    max_upload_mb: int = 500

    backup_dir: str = str(Path(__file__).resolve().parents[4] / "var" / "backups")

    # Video
    ffmpeg_bin: str = "ffmpeg"
    ffprobe_bin: str = "ffprobe"
    font_file: str = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    output_width: int = 1080
    output_height: int = 1920
    output_fps: int = 30
    mock_video_width: int = 1080
    mock_video_height: int = 1920
    default_scene_seconds: int = 8

    # AI
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-opus-5-5"
    usd_vnd_rate: int = 26000

    # Khởi tạo
    initial_admin_email: str = "admin@anhngan.local"
    initial_admin_password: str | None = None
    demo_user_password: str | None = None

    @property
    def broker_url(self) -> str:
        return self.celery_broker_url or self.redis_url

    @property
    def result_backend(self) -> str:
        return self.celery_result_backend or self.redis_url

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
