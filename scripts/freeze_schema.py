"""Sinh DDL đóng băng cho migration 0001 (chỉ dùng khi khởi tạo; migration sau dùng alembic revision)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "api"))

from sqlalchemy import create_mock_engine  # noqa: E402

from app.db.models import Base  # noqa: E402

out: list[str] = []
eng = create_mock_engine("postgresql+psycopg://", lambda sql, *a, **k: out.append(str(sql.compile(dialect=eng.dialect)).strip() + ";"))
Base.metadata.create_all(eng, checkfirst=False)
(ROOT / "migrations/sql/0001_initial_schema.sql").write_text(
    "-- Đóng băng từ SQLAlchemy metadata. KHÔNG sửa; tạo migration mới cho thay đổi.\n" + "\n\n".join(out) + "\n", encoding="utf-8"
)
print(f"{len(out)} statements")
