"""Sao lưu / khôi phục PostgreSQL bằng pg_dump/pg_restore (+ tuỳ chọn nén thư mục media local)."""
import hashlib
import os
import subprocess
import tarfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from app.core.config import get_settings
from app.core.errors import NotFound, ValidationFailed

SAFE_NAME = __import__("re").compile(r"^anngan_\d{8}_\d{6}(_[a-z]+)?\.(dump|tar\.gz)$")


def _libpq_url() -> str:
    return get_settings().database_url.replace("postgresql+psycopg://", "postgresql://")


def _env() -> dict:
    u = urlparse(_libpq_url())
    env = dict(os.environ)
    if u.password:
        env["PGPASSWORD"] = u.password
    return env


def _conn_args() -> list[str]:
    u = urlparse(_libpq_url())
    return ["-h", u.hostname or "localhost", "-p", str(u.port or 5432), "-U", u.username or "postgres", "-d", u.path.lstrip("/")]


def backup_dir() -> Path:
    d = Path(get_settings().backup_dir)
    d.mkdir(parents=True, exist_ok=True)
    return d


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def create_backup(include_media: bool = False) -> dict:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out = backup_dir() / f"anngan_{stamp}.dump"
    r = subprocess.run(["pg_dump", "-Fc", "--no-owner", "--no-privileges", "-f", str(out), *_conn_args()],
                       env=_env(), capture_output=True, text=True, timeout=1800)
    if r.returncode != 0:
        raise ValidationFailed(f"pg_dump lỗi: {r.stderr[-500:]}", code="BACKUP_FAILED")
    result = {"file_name": out.name, "size_bytes": out.stat().st_size, "checksum": sha256(out)}
    s = get_settings()
    if include_media and s.storage_backend == "local":
        media = backup_dir() / f"anngan_{stamp}_media.tar.gz"
        with tarfile.open(media, "w:gz") as tar:
            tar.add(s.storage_local_root, arcname="storage")
        result["media_file"] = media.name
    return result


def resolve_backup(file_name: str) -> Path:
    if not SAFE_NAME.match(file_name):
        raise ValidationFailed("Tên file backup không hợp lệ")
    p = backup_dir() / file_name
    if not p.exists():
        raise NotFound("Không tìm thấy file backup")
    return p


def restore_backup(file_name: str) -> None:
    p = resolve_backup(file_name)
    if not file_name.endswith(".dump"):
        raise ValidationFailed("Chỉ khôi phục file .dump")
    from app.db.session import reset_engine

    reset_engine()
    r = subprocess.run(["pg_restore", "--clean", "--if-exists", "--no-owner", "--no-privileges", "--single-transaction",
                        *_conn_args(), str(p)], env=_env(), capture_output=True, text=True, timeout=3600)
    if r.returncode != 0:
        raise ValidationFailed(f"pg_restore lỗi: {r.stderr[-800:]}", code="RESTORE_FAILED")


def list_files() -> list[dict]:
    out = []
    for p in sorted(backup_dir().glob("anngan_*"), reverse=True):
        out.append({"file_name": p.name, "size_bytes": p.stat().st_size,
                    "created_at": datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc).isoformat()})
    return out
