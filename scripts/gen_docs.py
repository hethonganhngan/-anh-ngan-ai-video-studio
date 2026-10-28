"""Sinh tài liệu tự động từ mã nguồn: docs/api/openapi.json, docs/api/ENDPOINTS.md, docs/database/ERD.md."""
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "api"))

from app.db.models import Base  # noqa: E402
from app.main import create_app  # noqa: E402

app = create_app()
spec = app.openapi()
(ROOT / "docs/api/openapi.json").write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")

by_tag = defaultdict(list)
for path, ops in spec["paths"].items():
    for method, op in ops.items():
        by_tag[(op.get("tags") or ["Khác"])[0]].append((method.upper(), path, op.get("summary", "")))
lines = ["# Danh mục API (sinh tự động từ OpenAPI)", "",
         f"Tổng: **{sum(len(v) for v in by_tag.values())} endpoint**. Base URL: `/api/v1`. Tài liệu tương tác: `/docs` (Swagger UI).", "",
         "Xác thực: cookie httpOnly `an_access` + header `X-CSRF-Token` (giá trị cookie `an_csrf`) cho request thay đổi dữ liệu, "
         "hoặc `Authorization: Bearer <token>` cho tích hợp máy-máy. Lỗi chuẩn: `{\"error\": {\"code\", \"message\", \"details\"}}`.", ""]
for tag in sorted(by_tag):
    lines += [f"## {tag}", "", "| Method | Path | Mô tả |", "|---|---|---|"]
    lines += [f"| `{m}` | `{p}` | {s} |" for m, p, s in sorted(by_tag[tag], key=lambda x: (x[1], x[0]))]
    lines.append("")
(ROOT / "docs/api/ENDPOINTS.md").write_text("\n".join(lines), encoding="utf-8")

er = ["# Sơ đồ cơ sở dữ liệu (sinh tự động từ SQLAlchemy metadata)", "",
      f"PostgreSQL 16 · **{len(Base.metadata.tables)} bảng** · khoá chính UUID · migration Alembic tại `migrations/`.", "",
      "```mermaid", "erDiagram"]
rels = set()
for t in sorted(Base.metadata.sorted_tables, key=lambda x: x.name):
    er.append(f"  {t.name} {{")
    for c in t.columns:
        typ = str(c.type).split("(")[0].replace(" ", "_").lower()
        flags = " PK" if c.primary_key else (" FK" if c.foreign_keys else "")
        er.append(f"    {typ} {c.name}{flags}")
    er.append("  }")
    for fk in t.foreign_keys:
        if fk.column.table.name != t.name:
            rels.add(f"  {fk.column.table.name} ||--o{{ {t.name} : \"{fk.parent.name}\"")
er += sorted(rels) + ["```", ""]
er += ["## Danh sách bảng", "", "| Bảng | Số cột | Ghi chú |", "|---|---|---|"]
for t in sorted(Base.metadata.sorted_tables, key=lambda x: x.name):
    notes = []
    cols = {c.name for c in t.columns}
    if "data_mode" in cols:
        notes.append("tách DEMO/PRODUCTION")
    if "deleted_at" in cols:
        notes.append("soft delete")
    if "version_no" in cols:
        notes.append("có phiên bản")
    if t.name in ("character_locks", "voice_locks", "scene_locks", "prompt_versions", "script_versions"):
        notes.append("bất biến sau duyệt (trigger)")
    if t.name == "audit_logs":
        notes.append("append-only (trigger)")
    er.append(f"| `{t.name}` | {len(t.columns)} | {', '.join(notes)} |")
(ROOT / "docs/database/ERD.md").write_text("\n".join(er) + "\n", encoding="utf-8")
print(f"OK: {sum(len(v) for v in by_tag.values())} endpoints, {len(Base.metadata.tables)} tables")
