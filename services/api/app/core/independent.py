"""Ghi bản ghi bằng session độc lập — dùng cho log lỗi/audit phải tồn tại kể cả khi transaction chính rollback."""
import logging

from app.db.session import SessionLocal

log = logging.getLogger("anngan.independent")


def persist(*objs) -> None:
    db = SessionLocal()
    try:
        for o in objs:
            db.merge(o)
        db.commit()
    except Exception:  # pragma: no cover - không được làm hỏng luồng chính
        db.rollback()
        log.exception("persist independent failed")
    finally:
        db.close()
