"""Ánh Ngân AI Video Studio — FastAPI entrypoint (Modular Monolith)."""
import logging
import time
import uuid

from app.api.health import LATENCY, REQUESTS
from app.api.health import router as health_router
from app.api.router import api_router
from app.core.config import get_settings
from app.core.errors import AppError
from app.core.logging import setup_logging
from app.core.rate_limit import hit
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import DBAPIError, IntegrityError

log = logging.getLogger("anngan.api")


def _check_production_secrets(s) -> None:
    """PRODUCTION không được chạy với khoá mặc định/yếu."""
    if s.environment != "production":
        return
    problems = []
    if s.secret_key.startswith("CHANGE_ME") or len(s.secret_key) < 32:
        problems.append("SECRET_KEY")
    if not s.encryption_key or s.encryption_key.startswith("CHANGE_ME"):
        problems.append("ENCRYPTION_KEY")
    if problems:
        raise RuntimeError(f"Cấu hình không an toàn cho production: đặt {', '.join(problems)} trong .env")


def create_app() -> FastAPI:
    s = get_settings()
    _check_production_secrets(s)
    setup_logging()
    app = FastAPI(
        title=s.app_name,
        version=s.app_version,
        description="API sản xuất video AI của Hệ thống Sữa Ánh Ngân. Tài liệu: /docs",
        docs_url="/docs",
        openapi_url="/openapi.json",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=s.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID", "Content-Disposition"],
    )

    @app.middleware("http")
    async def request_middleware(request: Request, call_next):
        rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:16]
        start = time.perf_counter()
        if request.url.path.startswith("/api/") and request.method != "OPTIONS":
            ip = request.client.host if request.client else "unknown"
            ok, _ = hit(f"api:{ip}", s.api_rate_limit_per_minute)
            if not ok:
                return JSONResponse(status_code=429, content={"error": {"code": "RATE_LIMITED", "message": "Quá nhiều yêu cầu"}})
        response = await call_next(request)
        dur = time.perf_counter() - start
        route = request.scope.get("route")
        route_path = getattr(route, "path", "unmatched")
        REQUESTS.labels(request.method, route_path, response.status_code).inc()
        LATENCY.labels(request.method, route_path).observe(dur)
        response.headers["X-Request-ID"] = rid
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        if response.status_code >= 500:
            log.error("request failed", extra={"request_id": rid, "path": request.url.path, "status": response.status_code})
        return response

    @app.exception_handler(AppError)
    async def app_error_handler(_: Request, exc: AppError):
        return JSONResponse(status_code=exc.status_code,
                            content={"error": {"code": exc.code, "message": exc.message, "details": exc.details}})

    @app.exception_handler(RequestValidationError)
    async def validation_handler(_: Request, exc: RequestValidationError):
        details = [{"field": ".".join(str(x) for x in e["loc"][1:]), "message": e["msg"]} for e in exc.errors()]
        return JSONResponse(status_code=422, content={"error": {"code": "VALIDATION_FAILED",
                                                                "message": "Dữ liệu không hợp lệ", "details": details}})

    @app.exception_handler(IntegrityError)
    async def integrity_handler(_: Request, exc: IntegrityError):
        log.warning("integrity error: %s", str(exc.orig)[:300])
        return JSONResponse(status_code=409, content={"error": {"code": "CONFLICT", "message": "Dữ liệu trùng hoặc vi phạm ràng buộc"}})

    @app.exception_handler(DBAPIError)
    async def dbapi_handler(_: Request, exc: DBAPIError):
        msg = str(exc.orig)
        for marker in ("IMMUTABLE_LOCK", "IMMUTABLE_PROMPT", "IMMUTABLE_SCRIPT_VERSION", "AUDIT_APPEND_ONLY"):
            if marker in msg:
                return JSONResponse(status_code=409, content={"error": {"code": marker, "message": msg.split("\n")[0]}})
        log.exception("database error")
        return JSONResponse(status_code=500, content={"error": {"code": "DATABASE_ERROR", "message": "Lỗi cơ sở dữ liệu"}})

    app.include_router(health_router)
    app.include_router(api_router, prefix="/api/v1")
    return app


app = create_app()
