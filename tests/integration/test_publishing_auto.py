"""M10 tự động: duyệt video → bài đăng + lịch + gói xuất; kênh M13 gắn Fanpage; Facebook chỉ nhận BẢN NHÁP chờ duyệt."""
import json

import httpx
import pytest

from tests.integration.test_publishing_analytics import _approved

PAGE = "1234567890"


class FakeGraph:
    """Giả lập Graph API — ghi lại mọi request, không gọi Facebook thật."""

    def __init__(self):
        self.calls, self.state = [], "draft"

    def __call__(self, req: httpx.Request) -> httpx.Response:
        self.calls.append(req)
        path = req.url.path
        if path.endswith("/me/accounts"):
            return httpx.Response(200, json={"data": [{"id": PAGE, "name": "Sữa Ánh Ngân", "tasks": ["CREATE_CONTENT"]}]})
        if path.endswith(f"/{PAGE}") and req.method == "GET":
            return httpx.Response(200, json={"id": PAGE, "name": "Sữa Ánh Ngân", "access_token": "PAGE-TOKEN"})
        if path.endswith(f"/{PAGE}/video_reels"):
            body = json.loads(req.content) if req.headers.get("content-type") == "application/json" else {}
            if body.get("upload_phase") == "start":
                return httpx.Response(200, json={"video_id": "777", "upload_url": "https://rupload.facebook.com/x"})
            return httpx.Response(200, json={"success": True})
        if req.url.host == "rupload.facebook.com":
            return httpx.Response(200, json={"success": True})
        if path.endswith("/777"):
            return httpx.Response(200, json={"permalink_url": "/reel/777", "status": {
                "video_status": "ready", "publishing_phase": {"status": "completed", "publish_status": self.state}}})
        return httpx.Response(404, json={"error": {"message": "unknown", "code": 100}})


@pytest.fixture
def graph(monkeypatch):
    from app.modules.publishing import service

    g = FakeGraph()
    monkeypatch.setattr(service, "_fb_http", httpx.Client(transport=httpx.MockTransport(g)))
    return g


def test_slot_parsing_and_hashtags():
    from app.modules.publishing.service import _slot, _slug_tag

    assert _slot(["Đăng 18:00–21:00"]) == (18, 0)
    assert _slot(["Chỉ đăng video đã duyệt", "Đăng tối"]) == (19, 0)
    assert _slot([]) == (19, 0)
    assert _slug_tag("Hệ thống Sữa Ánh Ngân") == "#HeThongSuaAnhNgan"


def test_approved_video_is_auto_prepared(login, channels):
    pub = login("publisher")
    pid = _approved(login, channels, "Mẹo cho bé ngủ ngon giấc")
    items = [x for x in pub.get("/publications/calendar").json() if x["project_id"] == pid]
    assert {x["platform"] for x in items} == set(channels["KTMB"]["platforms"])
    for x in items:
        assert x["status"] == "EXPORTED" and x["export_asset_id"] and x["scheduled_at"]
        assert "minh hoạ" in x["caption"] and "#KienThucMeBe" in x["hashtags"]
    days = {x["scheduled_at"][:10] for x in items if x["platform"] == "TIKTOK"}
    assert len(days) == 1
    # Chạy lại không tạo trùng; video thứ 2 cùng kênh lùi sang ngày khác (1 bài/ngày/nền tảng)
    assert login("pm").post(f"/publications/auto-prepare/{pid}").json() == []
    pid2 = _approved(login, channels, "Lịch ăn dặm tuần đầu")
    t1 = next(x for x in items if x["platform"] == "TIKTOK")["scheduled_at"]
    t2 = next(x for x in pub.get("/publications/calendar").json() if x["project_id"] == pid2 and x["platform"] == "TIKTOK")
    assert t2["scheduled_at"][:10] != t1[:10]


def test_channel_connects_facebook_and_sends_draft_only(login, channels, graph):
    from app.core.context import SYSTEM_ACTOR, Ctx
    from app.db.session import SessionLocal
    from app.modules.publishing import service
    from app.modules.publishing.models import Publication

    admin = login("admin")
    fb = next(x for x in admin.get("/admin/providers").json() if x["provider_code"] == "facebook_pages")
    admin.patch(f"/admin/providers/{fb['id']}", json={"api_key": "USER-TOKEN-xyz", "is_enabled": True})
    assert admin.post(f"/admin/providers/{fb['id']}/test").json()["connection_status"] == "VERIFIED"
    assert admin.get("/channels/facebook/pages").json()[0]["id"] == PAGE
    ch = admin.put(f"/channels/{channels['KTMB']['id']}/facebook", json={"page_id": PAGE}).json()
    assert ch["publish_targets"]["FACEBOOK"]["page_name"] == "Sữa Ánh Ngân"
    assert admin.put(f"/channels/{channels['KTMB']['id']}/facebook", json={"page_id": "abc"}).status_code == 422

    pid = _approved(login, channels, "Bé biếng ăn mẹ nên làm gì")
    fb_pub = next(x for x in login("publisher").get("/publications/calendar").json()
                  if x["project_id"] == pid and x["platform"] == "FACEBOOK")
    assert fb_pub["publish_mode"] == "API"
    # Dữ liệu DEMO không bao giờ lên Facebook
    r = login("pm").post(f"/publications/{fb_pub['id']}/facebook-draft")
    assert r.json()["error"]["code"] == "DEMO_AUTO_PUBLISH_BLOCKED"

    db = SessionLocal()
    try:  # mô phỏng PRODUCTION
        from app.modules.projects.models import Project

        p = db.get(Publication, fb_pub["id"])
        p.data_mode = db.get(Project, p.project_id).data_mode = "PRODUCTION"
        db.commit()
        ctx = Ctx(db=db, actor=SYSTEM_ACTOR, mode="PRODUCTION")
        x = service.send_facebook_draft(ctx, p.id)
        db.commit()
        assert x.status == "PENDING_REVIEW" and x.external_id == "777"
        from urllib.parse import parse_qs

        forms = [parse_qs(c.content.decode()) for c in graph.calls
                 if c.url.path.endswith("/video_reels") and c.headers.get("content-type", "").startswith("application/x-www")]
        assert forms and forms[0]["upload_phase"] == ["finish"] and forms[0]["video_state"] == ["DRAFT"]
        assert forms[0]["is_ai_generated"] == ["true"] and "minh hoạ" in forms[0]["description"][0]
        assert not any("PUBLISHED" in str(f.get("video_state")) for f in forms)
        # Token không bao giờ nằm trên URL (tránh lộ qua log)
        assert not any("TOKEN" in str(c.url) for c in graph.calls)
        up = next(c for c in graph.calls if c.url.host == "rupload.facebook.com")
        assert up.headers["Authorization"] == "OAuth PAGE-TOKEN"
        # Chưa duyệt trên Facebook → vẫn chờ; duyệt xong → PUBLISHED + URL thật
        assert service.sync_facebook(ctx, p.id).status == "PENDING_REVIEW"
        graph.state = "published"
        x = service.sync_facebook(ctx, p.id)
        db.commit()
        assert x.status == "PUBLISHED" and x.post_url == "https://www.facebook.com/reel/777"
    finally:
        db.close()
    admin.put(f"/channels/{channels['KTMB']['id']}/facebook", json={"page_id": None})
    admin.patch(f"/admin/providers/{fb['id']}", json={"clear_api_key": True})
