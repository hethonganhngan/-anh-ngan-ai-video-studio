"""veo_vertex: chuyển từ cấu hình submit_url/status_url sang adapter Vertex AI (service account)

Revision ID: 0003
Revises: 0002
"""
import json

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

CONFIG = {
    "adapter": "veo_vertex", "model": "veo-3.1-fast-generate-001", "location": "us-central1", "resolution": "720p",
    "generate_audio": True, "max_duration_sec": 8, "supported_aspects": ["9:16", "16:9"],
    "note": "Dùng được tín dụng dùng thử Google Cloud. Bật Vertex AI API, tạo service account (Vertex AI User) và "
            "nạp file khoá JSON tại 'Sửa'. Giá Veo 3.1 Fast có tiếng ~0,15 USD/giây (tham khảo, kiểm tra bảng giá Google).",
}


def upgrade() -> None:
    # Chỉ sửa bản ghi chưa có adapter (chưa từng cấu hình) — không ghi đè cấu hình người dùng đã chỉnh
    op.get_bind().execute(
        sa.text("UPDATE provider_accounts SET config = CAST(:cfg AS jsonb), unit_cost = 3900 "
                "WHERE provider_code = 'veo_vertex' AND secret_encrypted IS NULL AND NOT (config ? 'adapter')"),
        {"cfg": json.dumps(CONFIG, ensure_ascii=False)},
    )


def downgrade() -> None:
    pass
