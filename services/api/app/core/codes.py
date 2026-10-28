"""Sinh mã nghiệp vụ dễ đọc: PRJ-2610-0001, FB-2610-0001..."""
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session


def next_code(db: Session, model, prefix: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%y%m")
    base = f"{prefix}-{stamp}-"
    last = db.scalar(select(func.max(model.code)).where(model.code.like(f"{base}%")))
    n = int(last.rsplit("-", 1)[1]) + 1 if last else 1
    return f"{base}{n:04d}"
