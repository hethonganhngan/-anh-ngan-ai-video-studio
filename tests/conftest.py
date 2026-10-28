"""Cấu hình test: DB anngan_test, Celery eager, storage tạm, video mock độ phân giải thấp để chạy nhanh."""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TMP = Path(tempfile.mkdtemp(prefix="anngan_test_"))
os.environ.update({
    "ENVIRONMENT": "test",
    "DATABASE_URL": os.environ.get("TEST_DATABASE_URL", "postgresql+psycopg://anngan:anngan@localhost:5432/anngan_test"),
    "CELERY_TASK_ALWAYS_EAGER": "true",
    "STORAGE_BACKEND": "local",
    "STORAGE_LOCAL_ROOT": str(TMP / "storage"),
    "BACKUP_DIR": str(TMP / "backups"),
    "MOCK_VIDEO_WIDTH": "360", "MOCK_VIDEO_HEIGHT": "640",
    "OUTPUT_WIDTH": "540", "OUTPUT_HEIGHT": "960",
    "SECRET_KEY": "test-secret-key-0123456789-abcdefghijklmnop",
    "INITIAL_ADMIN_EMAIL": "admin@anhngan.local",
    "INITIAL_ADMIN_PASSWORD": "Admin@12345678",
    "DEMO_USER_PASSWORD": "Demo@12345678",
    "LOGIN_RATE_LIMIT_PER_MINUTE": "1000",
    "API_RATE_LIMIT_PER_MINUTE": "100000",
})
sys.path[:0] = [str(ROOT / "services" / "api"), str(ROOT / "services" / "worker")]

import pytest  # noqa: E402


def _reset_db():
    from sqlalchemy import create_engine, text

    url = os.environ["DATABASE_URL"]
    eng = create_engine(url)
    with eng.begin() as c:
        c.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public;"))
    eng.dispose()
    subprocess.run([sys.executable, "-m", "alembic", "-c", str(ROOT / "services/api/alembic.ini"), "upgrade", "head"],
                   cwd=ROOT / "services/api", check=True, env=os.environ.copy(), capture_output=True)


@pytest.fixture(scope="session", autouse=True)
def database():
    from app.core.config import get_settings

    get_settings.cache_clear()
    _reset_db()
    from app.db.session import reset_engine
    from app.seed.seed import run

    reset_engine()
    run(with_demo_users=True)
    yield
    reset_engine()
    shutil.rmtree(TMP, ignore_errors=True)


@pytest.fixture(scope="session")
def app(database):
    from app.main import create_app

    return create_app()


class Api:
    def __init__(self, client, token: str):
        self.c = client
        self.h = {"Authorization": f"Bearer {token}"}

    def get(self, url, **kw):
        return self.c.get(f"/api/v1{url}", headers=self.h, **kw)

    def post(self, url, json=None, **kw):
        return self.c.post(f"/api/v1{url}", headers=self.h, json=json, **kw)

    def put(self, url, json=None, **kw):
        return self.c.put(f"/api/v1{url}", headers=self.h, json=json, **kw)

    def patch(self, url, json=None, **kw):
        return self.c.patch(f"/api/v1{url}", headers=self.h, json=json, **kw)

    def delete(self, url, **kw):
        return self.c.delete(f"/api/v1{url}", headers=self.h, **kw)


ROLE_USERS = {
    "admin": ("admin@anhngan.local", "Admin@12345678"),
    "pm": ("pm@anhngan.local", "Demo@12345678"),
    "sysadmin": ("sysadmin@anhngan.local", "Demo@12345678"),
    "creator": ("creator@anhngan.local", "Demo@12345678"),
    "editor": ("editor@anhngan.local", "Demo@12345678"),
    "qc": ("qc@anhngan.local", "Demo@12345678"),
    "publisher": ("publisher@anhngan.local", "Demo@12345678"),
    "viewer": ("viewer@anhngan.local", "Demo@12345678"),
}


@pytest.fixture(scope="session")
def client(app):
    from fastapi.testclient import TestClient

    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def login(client):
    cache = {}

    def _login(role: str) -> Api:
        if role not in cache:
            email, pwd = ROLE_USERS[role]
            r = client.post("/api/v1/auth/login", json={"email": email, "password": pwd})
            assert r.status_code == 200, r.text
            cache[role] = r.json()["access_token"]
        return Api(client, cache[role])

    return _login


@pytest.fixture(scope="session")
def admin(login):
    return login("admin")


@pytest.fixture(scope="session")
def channels(admin):
    return {c["code"]: c for c in admin.get("/channels").json()}
