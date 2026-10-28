"""Đăng nhập, khoá tài khoản, CSRF, thu hồi token, RBAC, phê duyệt trái quyền."""
import pytest

from tests.helpers import create_project


def test_login_wrong_password_and_lockout(client, admin):
    r = admin.post("/admin/users", json={"email": "lock@anhngan.local", "full_name": "Khoá Thử", "role_code": "VIEWER",
                                          "password": "Lockme@12345"})
    assert r.status_code == 201, r.text
    for _ in range(5):
        r = client.post("/api/v1/auth/login", json={"email": "lock@anhngan.local", "password": "sai"})
        assert r.status_code == 401
    r = client.post("/api/v1/auth/login", json={"email": "lock@anhngan.local", "password": "Lockme@12345"})
    assert r.status_code == 401 and r.json()["error"]["code"] == "ACCOUNT_LOCKED"


def test_unauthenticated_requests_rejected(app):
    from fastapi.testclient import TestClient

    with TestClient(app) as c:
        assert c.get("/api/v1/projects").status_code == 401
        assert c.get("/api/v1/projects", headers={"Authorization": "Bearer abc.def.ghi"}).status_code == 401


def test_cookie_auth_requires_csrf(app):
    from fastapi.testclient import TestClient

    with TestClient(app) as c:
        r = c.post("/api/v1/auth/login", json={"email": "pm@anhngan.local", "password": "Demo@12345678"})
        assert r.status_code == 200 and "an_access" in c.cookies and "an_csrf" in c.cookies
        assert c.get("/api/v1/auth/me").status_code == 200  # GET không cần CSRF
        r = c.post("/api/v1/feedback", json={"source": "INTERNAL", "title": "CSRF test"})
        assert r.status_code == 403 and r.json()["error"]["code"] == "CSRF_FAILED"
        r = c.post("/api/v1/feedback", json={"source": "INTERNAL", "title": "CSRF test"},
                   headers={"X-CSRF-Token": c.cookies["an_csrf"]})
        assert r.status_code == 201


def test_password_change_revokes_old_tokens(client, admin):
    admin.post("/admin/users", json={"email": "pw@anhngan.local", "full_name": "Đổi MK", "role_code": "VIEWER",
                                     "password": "Oldpass@1234"})
    tok = client.post("/api/v1/auth/login", json={"email": "pw@anhngan.local", "password": "Oldpass@1234"}).json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    me = client.get("/api/v1/auth/me", headers=h).json()
    assert me["must_change_password"] is True
    r = client.post("/api/v1/auth/change-password", headers=h, json={"current_password": "Oldpass@1234", "new_password": "weak"})
    assert r.status_code == 422
    r = client.post("/api/v1/auth/change-password", headers=h, json={"current_password": "Oldpass@1234", "new_password": "Newpass@5678"})
    assert r.status_code == 200
    r = client.get("/api/v1/auth/me", headers=h)
    assert r.status_code == 401 and r.json()["error"]["code"] == "TOKEN_REVOKED"


@pytest.mark.parametrize("role,method,url,body,expected", [
    ("viewer", "post", "/projects", {"channel_id": "00000000-0000-0000-0000-000000000000", "topic": "abcdef"}, 403),
    ("viewer", "get", "/admin/users", None, 403),
    ("creator", "get", "/admin/audit-logs", None, 403),
    ("creator", "post", "/admin/mode", {"mode": "PRODUCTION", "confirm_text": "PRODUCTION"}, 403),
    ("editor", "post", "/lessons", {"lesson_type": "ROOT_CAUSE", "title": "x" * 5, "lesson": "y" * 5}, 403),
    ("publisher", "post", "/feedback/00000000-0000-0000-0000-000000000000/capa/approve", {"note": ""}, 403),
    ("qc", "post", "/admin/backups", {}, 403),
    ("sysadmin", "post", "/projects/00000000-0000-0000-0000-000000000000/approve", {"decision": "APPROVED"}, 403),
    ("viewer", "get", "/dashboard", None, 200),
    ("viewer", "get", "/projects", None, 200),
])
def test_rbac_matrix(login, role, method, url, body, expected):
    api = login(role)
    r = getattr(api, method)(url, json=body) if body is not None else getattr(api, method)(url)
    assert r.status_code == expected, (role, url, r.text)


def test_creator_cannot_approve_script_or_publish(login, channels):
    creator, pm = login("creator"), login("pm")
    p = create_project(creator, channels["KTMB"]["id"], topic="Chăm sóc da bé mùa hanh khô", automation_level="MANUAL")
    creator.post(f"/projects/{p['id']}/script/ideas")
    creator.post(f"/projects/{p['id']}/script/select-idea", json={"index": 1})
    assert creator.post(f"/projects/{p['id']}/script/write").status_code == 200
    r = creator.post(f"/projects/{p['id']}/script/approve", json={"comment": ""})
    assert r.status_code == 403 and r.json()["error"]["code"] == "PERMISSION_DENIED"
    assert pm.post(f"/projects/{p['id']}/script/approve", json={"comment": ""}).status_code == 200


def test_sysadmin_cannot_create_super_admin(login):
    sa = login("sysadmin")
    r = sa.post("/admin/users", json={"email": "boss2@anhngan.local", "full_name": "Sếp giả", "role_code": "SUPER_ADMIN",
                                       "password": "Boss@123456789"})
    assert r.status_code == 422


def test_rate_limit_login(client, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "login_rate_limit_per_minute", 3)
    codes = [client.post("/api/v1/auth/login", json={"email": "rl@anhngan.local", "password": "x"}).status_code for _ in range(5)]
    assert codes[:3] == [401, 401, 401] and 429 in codes[3:]
