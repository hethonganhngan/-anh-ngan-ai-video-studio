"""Character Lock / Voice Lock / Scene Lock: phiên bản bất biến, duyệt 4 mắt, consent, ảnh hưởng tới tạo cảnh."""
import pytest
from sqlalchemy import text

from tests.helpers import create_project, make_audio, make_png, upload


def _char_with_refs(pm, channel_id, name="Chị Ngân – tư vấn viên"):
    r = pm.post("/characters", json={"name": name, "channel_id": channel_id, "appearance": "Nữ 30 tuổi, tóc búi gọn, gương mặt hiền",
                                      "outfit": "Áo đồng phục xanh Ánh Ngân, bảng tên", "expressions": ["mỉm cười", "lắng nghe"],
                                      "consent_status": "GRANTED", "usage_rights": "Hợp đồng hình ảnh 2026"})
    assert r.status_code == 201, r.text
    c = r.json()
    for ref in ("FRONT", "THREE_QUARTER", "FULL_BODY"):
        a = upload(pm, make_png(f"{ref}.png"), "CHARACTER", usage_rights="CONSENTED").json()
        assert pm.post(f"/characters/{c['id']}/references", json={"ref_type": ref, "asset_id": a["id"]}).status_code == 201
    return c


def test_character_lock_lifecycle(login, channels):
    pm, admin = login("pm"), login("admin")
    c = _char_with_refs(pm, channels["ANNGAN"]["id"])
    assert c["code"].startswith("CHR-")
    d = pm.get(f"/characters/{c['id']}").json()
    assert d["readiness"]["ready"] is True

    lock = pm.post(f"/characters/{c['id']}/locks", json={"change_note": "Bản đầu"}).json()
    assert lock["status"] == "DRAFT" and lock["version_no"] == 1
    assert pm.post(f"/characters/{c['id']}/locks", json={}).status_code == 409  # đã có nháp
    r = pm.post(f"/character-locks/{lock['id']}/approve")
    assert r.status_code == 422 and r.json()["error"]["code"] == "SELF_APPROVAL"
    assert login("creator").post(f"/character-locks/{lock['id']}/approve").status_code == 403
    r = admin.post(f"/character-locks/{lock['id']}/approve")
    assert r.status_code == 200 and r.json()["status"] == "APPROVED"
    d = pm.get(f"/characters/{c['id']}").json()
    assert d["character"]["status"] == "LOCKED" and d["character"]["active_lock_id"] == lock["id"]

    # Sửa hồ sơ không làm thay đổi lock đã duyệt
    pm.patch(f"/characters/{c['id']}", json={"outfit": "Áo khoác trắng"})
    d = pm.get(f"/characters/{c['id']}").json()
    assert d["locks"][0]["lock_data"]["outfit"].startswith("Áo đồng phục")

    # Phiên bản mới → bản cũ RETIRED
    lock2 = pm.post(f"/characters/{c['id']}/locks", json={"change_note": "Đổi áo"}).json()
    admin.post(f"/character-locks/{lock2['id']}/approve")
    locks = {x["version_no"]: x["status"] for x in pm.get(f"/characters/{c['id']}").json()["locks"]}
    assert locks == {1: "RETIRED", 2: "APPROVED"}


def test_approved_lock_is_immutable_at_db_level(login, channels):
    pm, admin = login("pm"), login("admin")
    c = _char_with_refs(pm, channels["CNM"]["id"], name="Mẹ Lan")
    lock = pm.post(f"/characters/{c['id']}/locks", json={}).json()
    admin.post(f"/character-locks/{lock['id']}/approve")
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        with pytest.raises(Exception) as ei:
            db.execute(text("UPDATE character_locks SET lock_data = '{}'::jsonb WHERE id = :i"), {"i": lock["id"]})
            db.commit()
        assert "IMMUTABLE_LOCK" in str(ei.value)
    finally:
        db.rollback()
        db.close()


def test_lock_not_ready_without_references(login, channels):
    pm, admin = login("pm"), login("admin")
    c = pm.post("/characters", json={"name": "Thiếu ảnh", "appearance": "a", "outfit": "b", "consent_status": "PENDING"}).json()
    lock = pm.post(f"/characters/{c['id']}/locks", json={}).json()
    r = admin.post(f"/character-locks/{lock['id']}/approve")
    assert r.status_code == 422 and r.json()["error"]["code"] == "LOCK_NOT_READY"


def test_unlocked_character_blocks_generation(login, channels):
    pm = login("pm")
    c = pm.post("/characters", json={"name": "Nhân vật chưa khoá", "appearance": "x", "outfit": "y"}).json()
    p = create_project(pm, channels["ANNGAN"]["id"], topic="Mẹo bảo quản sữa bột đã pha", duration_sec=8,
                       character_ids=[c["id"]], automation_level="MANUAL")
    pm.post(f"/projects/{p['id']}/script/ideas")
    pm.post(f"/projects/{p['id']}/script/select-idea", json={"index": 0})
    pm.post(f"/projects/{p['id']}/script/write")
    pm.post(f"/projects/{p['id']}/script/approve", json={})
    rep = pm.post(f"/projects/{p['id']}/validate-assets").json()
    assert any("chưa có Character Lock" in b for b in rep["blocking"])
    assert pm.get(f"/projects/{p['id']}").json()["status"] == "NEEDS_MANUAL_ACTION"
    r = pm.post(f"/projects/{p['id']}/generate", json={})
    assert r.status_code == 409 and r.json()["error"]["code"] == "ASSET_VALIDATION_REQUIRED"


def test_voice_lock_requires_consent_and_audio(login):
    pm, admin = login("pm"), login("admin")
    v = pm.post("/voices", json={"name": "Giọng Ba Phi", "accent": "Miền Tây", "consent_status": "PENDING"}).json()
    r = pm.post(f"/voices/{v['id']}/locks", json={})
    assert r.status_code == 422 and r.json()["error"]["code"] == "LOCK_NOT_READY"
    audio = upload(pm, make_audio("ref.mp3"), "AUDIO", usage_rights="CONSENTED").json()
    pm.patch(f"/voices/{v['id']}", json={"consent_status": "GRANTED", "audio_reference_asset_id": audio["id"]})
    lock = pm.post(f"/voices/{v['id']}/locks", json={"change_note": "v1"}).json()
    assert lock["lock_data"]["audio_reference"]["checksum"] == audio["checksum_sha256"]
    assert admin.post(f"/voice-locks/{lock['id']}/approve").json()["status"] == "APPROVED"
    assert pm.get(f"/voices/{v['id']}").json()["voice"]["status"] == "LOCKED"


def test_delete_voice_blocked_while_in_use(login, channels):
    pm, creator = login("pm"), login("creator")
    v = pm.post("/voices", json={"name": "Giọng tạm", "accent": "Miền Nam"}).json()
    c = pm.post("/characters", json={"name": "Chị Mai", "appearance": "a", "outfit": "b", "voice_profile_id": v["id"]}).json()
    assert creator.delete(f"/voices/{v['id']}").status_code == 403
    r = pm.delete(f"/voices/{v['id']}")
    assert r.status_code == 409 and r.json()["error"]["code"] == "VOICE_IN_USE" and c["code"] in r.json()["error"]["message"]
    pm.patch(f"/characters/{c['id']}", json={"voice_profile_id": None})
    assert pm.delete(f"/voices/{v['id']}").json() == {"deleted": v["code"]}
    assert pm.get(f"/voices/{v['id']}").status_code == 404
    assert all(x["id"] != v["id"] for x in pm.get("/voices").json())


def test_scene_lock_versions(login, channels):
    pm, admin = login("pm"), login("admin")
    sl = pm.post("/scene-locks", json={"name": "Quầy tư vấn Ánh Ngân", "channel_id": channels["ANNGAN"]["id"],
                                        "setting": "Quầy tư vấn gỗ sáng, kệ sữa phía sau", "colors": "xanh dương, trắng"}).json()
    assert sl["version_no"] == 1 and sl["code"].startswith("SCN-")
    admin.post(f"/scene-locks/{sl['id']}/approve")
    sl2 = pm.post("/scene-locks", json={"name": "Quầy tư vấn Ánh Ngân", "setting": "Quầy mới", "base_code": sl["code"]}).json()
    assert sl2["version_no"] == 2 and sl2["code"] == sl["code"]
    admin.post(f"/scene-locks/{sl2['id']}/approve")
    all_v = {x["version_no"]: x["status"] for x in pm.get("/scene-locks?all_versions=true").json() if x["code"] == sl["code"]}
    assert all_v == {1: "RETIRED", 2: "APPROVED"}


def test_locked_character_flows_into_prompt(login, channels):
    pm, admin = login("pm"), login("admin")
    c = _char_with_refs(pm, channels["ANNGAN"]["id"], name="Chị Mai – dược sĩ")
    lock = pm.post(f"/characters/{c['id']}/locks", json={}).json()
    admin.post(f"/character-locks/{lock['id']}/approve")
    p = create_project(pm, channels["ANNGAN"]["id"], topic="Đọc nhãn sản phẩm đúng cách", duration_sec=8,
                       character_ids=[c["id"]], automation_level="MANUAL")
    pm.post(f"/projects/{p['id']}/script/ideas")
    pm.post(f"/projects/{p['id']}/script/select-idea", json={"index": 2})
    pm.post(f"/projects/{p['id']}/script/write")
    view = pm.post(f"/projects/{p['id']}/script/approve", json={}).json()
    prompt = view["scenes"][0]["prompt_text"]
    assert c["code"] in prompt and "Character Lock v1" in prompt
    rep = pm.post(f"/projects/{p['id']}/validate-assets").json()
    assert rep["blocking"] == []


def test_delete_character_blocked_while_project_uses_it(login, channels):
    pm = login("pm")
    c = pm.post("/characters", json={"name": "Chị Hoa", "appearance": "a", "outfit": "b"}).json()
    p = create_project(pm, channels["ANNGAN"]["id"], topic="Mẹo pha sữa đúng cách", duration_sec=8,
                       character_ids=[c["id"]], automation_level="MANUAL")
    r = pm.delete(f"/characters/{c['id']}")
    assert r.status_code == 409 and r.json()["error"]["code"] == "CHARACTER_IN_USE" and p["code"] in r.json()["error"]["message"]
    pm.post(f"/projects/{p['id']}/cancel", json={"note": "Thử xoá nhân vật"})
    assert pm.delete(f"/characters/{c['id']}").json() == {"deleted": c["code"]}
    assert pm.get(f"/characters/{c['id']}").status_code == 404
    assert all(x["id"] != c["id"] for x in pm.get("/characters").json())
