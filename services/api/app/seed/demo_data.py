"""Dữ liệu mẫu DEMO (gắn nhãn DEMO): nhân vật + Lock, giọng, bối cảnh, logo, dự án ở nhiều giai đoạn,
1 video đã đăng có analytics, 1 hồ sơ Feedback và bài học. Gọi qua API nội bộ để đi đủ validation.

Chạy: python -m app.seed.seed --demo-data   (chỉ khi hệ thống ở DEMO MODE)."""
import os
import subprocess
import tempfile
from pathlib import Path

from app.core.config import get_settings
from app.modules.administration.service import get_mode
from app.modules.rendering.ffmpeg import filter_path
from sqlalchemy.orm import Session

_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT = _BOLD if os.path.exists(_BOLD) else get_settings().font_file


def _ffmpeg(args: list[str]) -> None:
    subprocess.run([get_settings().ffmpeg_bin, "-loglevel", "error", "-y", *args], check=True)


def _png(d: Path, name: str, color: str, text: str, size: str = "720x960") -> Path:
    p = d / name
    tf = d / f"{name}.txt"
    tf.write_text(text, encoding="utf-8")
    _ffmpeg(["-f", "lavfi", "-i", f"color=c={color}:s={size}", "-vf",
             f"drawtext=fontfile={filter_path(FONT)}:textfile={filter_path(tf)}:fontcolor=white:fontsize=40:x=(w-tw)/2:y=(h-th)/2", "-frames:v", "1", str(p)])
    return p


def seed_demo_data(db: Session) -> None:
    if get_mode(db) != "DEMO":
        raise SystemExit("Chỉ tạo dữ liệu mẫu khi hệ thống ở DEMO MODE")
    from app.main import create_app
    from fastapi.testclient import TestClient

    s = get_settings()
    s.celery_task_always_eager = True
    from app.workflows.celery_client import reset_celery

    reset_celery()
    pwd = s.initial_admin_password
    if not pwd:
        raise SystemExit("Cần INITIAL_ADMIN_PASSWORD (hoặc mật khẩu Super Admin hiện tại) để tạo dữ liệu mẫu")
    tmp = Path(tempfile.mkdtemp(prefix="anngan_demo_"))
    with TestClient(create_app()) as c:
        tok = c.post("/api/v1/auth/login", json={"email": s.initial_admin_email, "password": pwd}).json()["access_token"]
        h = {"Authorization": f"Bearer {tok}"}

        def api(method, url, **kw):
            r = getattr(c, method)(f"/api/v1{url}", headers=h, **kw)
            if r.status_code >= 400:
                raise RuntimeError(f"{method} {url} → {r.status_code} {r.text[:300]}")
            return r.json()

        def upload(path: Path, asset_type: str, **form):
            with open(path, "rb") as f:
                return api("post", "/assets", files={"file": (path.name, f)}, data={"asset_type": asset_type, "tags": "demo", **form})

        ch = {x["code"]: x for x in api("get", "/channels")}
        upload(_png(tmp, "logo_anhngan.png", "0x1D4ED8", "ÁNH NGÂN", "400x400"), "LOGO", channel_id=ch["ANNGAN"]["id"],
                      usage_rights="OWNED", description="DEMO — logo mẫu")
        # Nhân vật mẫu + Character Lock
        chars = []
        for name, color, appearance, outfit in (
            ("Chị Ngân – tư vấn viên (DEMO)", "0x0F766E", "Nữ 30 tuổi, tóc búi gọn, nụ cười hiền", "Đồng phục xanh dương Ánh Ngân, bảng tên"),
            ("Mẹ Lan (DEMO)", "0x9D174D", "Nữ 28 tuổi, tóc ngang vai, gương mặt tròn", "Áo thun hồng nhạt, quần jean"),
        ):
            cobj = api("post", "/characters", json={"name": name, "channel_id": ch["ANNGAN"]["id"], "appearance": appearance,
                                                    "outfit": outfit, "expressions": ["mỉm cười", "lắng nghe"],
                                                    "consent_status": "GRANTED", "usage_rights": "DEMO — nhân vật minh hoạ"})
            for ref, label in (("FRONT", "Chính diện"), ("THREE_QUARTER", "Góc 3/4"), ("FULL_BODY", "Toàn thân")):
                a = upload(_png(tmp, f"{cobj['code']}_{ref}.png", color, f"{name}\n{label}"), "CHARACTER", usage_rights="CONSENTED")
                api("post", f"/characters/{cobj['id']}/references", json={"ref_type": ref, "asset_id": a["id"]})
            lock = api("post", f"/characters/{cobj['id']}/locks", json={"change_note": "DEMO v1"})
            api("post", f"/character-locks/{lock['id']}/approve")
            chars.append(cobj)
        # Giọng & bối cảnh mẫu
        audio = tmp / "giong_mau.mp3"
        _ffmpeg(["-f", "lavfi", "-i", "sine=frequency=520:duration=4", str(audio)])
        a = upload(audio, "AUDIO", usage_rights="CONSENTED", description="DEMO — audio tham chiếu giọng")
        v = api("post", "/voices", json={"name": "Giọng Chị Ngân (DEMO)", "accent": "Miền Trung", "gender": "Nữ",
                                         "tone": "Ấm áp, rõ ràng", "audio_reference_asset_id": a["id"], "consent_status": "GRANTED",
                                         "usage_rights": "DEMO"})
        vl = api("post", f"/voices/{v['id']}/locks", json={"change_note": "DEMO v1"})
        api("post", f"/voice-locks/{vl['id']}/approve")
        sl = api("post", "/scene-locks", json={"name": "Quầy tư vấn Ánh Ngân (DEMO)", "channel_id": ch["ANNGAN"]["id"],
                                               "setting": "Quầy tư vấn gỗ sáng màu, kệ sản phẩm gọn gàng phía sau",
                                               "lighting": "Ánh sáng ấm, đều", "props": "Bảng tên, sổ tư vấn", "colors": "xanh dương, trắng"})
        api("post", f"/scene-locks/{sl['id']}/approve")
        # Dự án ở các giai đoạn
        base = {"channel_id": ch["ANNGAN"]["id"], "character_ids": [x["id"] for x in chars], "scene_lock_ids": [sl["id"]],
                "voice_profile_id": v["id"], "cta": "Ghé Ánh Ngân hoặc nhắn tin để được tư vấn theo nhu cầu của bé nhé",
                "budget_limit": 200000}
        p1 = api("post", "/projects", json={**base, "topic": "Cách đọc nhãn và hạn dùng khi chọn tã cho bé", "duration_sec": 16})["projects"][0]
        api("post", f"/projects/{p1['id']}/advance")  # A02 → SCRIPT_REVIEW
        api("post", f"/projects/{p1['id']}/script/approve", json={"comment": "DEMO"})
        api("post", f"/projects/{p1['id']}/advance")  # → FINAL_QC
        q = api("get", f"/projects/{p1['id']}/qc")
        auto = q["agent_final"]["scores"]
        keys = ["hook", "script", "character", "setting", "visual", "voice", "lipsync", "audio", "brand", "compliance"]
        scores = {k: {"score": auto[k]["score"] if auto[k]["method"] == "AUTO" else 10} for k in keys}
        api("post", f"/projects/{p1['id']}/qc/final", json={"scores": scores, "notes": "DEMO đạt chuẩn"})
        api("post", f"/projects/{p1['id']}/approve", json={"decision": "APPROVED", "comment": "DEMO"})
        pub = api("post", "/publications", json={"project_id": p1["id"], "platform": "FACEBOOK", "caption": "Ánh Ngân đồng hành cùng mẹ chọn tã thoáng mát (DEMO)",
                                                 "hashtags": ["anhngan", "mevabe"]})
        api("post", f"/publications/{pub['id']}/mark-published", json={"post_url": "https://www.facebook.com/anhngan.demo/videos/1"})
        api("post", f"/publications/{pub['id']}/snapshots", json={"views": 2400, "likes": 180, "comments": 26, "shares": 14, "saves": 9,
                                                                  "retention_rate": 38.5, "conversions": 5})
        p2 = api("post", "/projects", json={**base, "topic": "Bảo quản sữa bột đã mở hộp đúng cách", "duration_sec": 24})["projects"][0]
        api("post", f"/projects/{p2['id']}/advance")
        p3 = api("post", "/projects", json={**base, "channel_id": ch["KTMB"]["id"], "topic": "Dấu hiệu bé mọc răng và cách chăm sóc nướu",
                                            "duration_sec": 16, "automation_level": "MANUAL"})["projects"][0]
        api("post", f"/projects/{p3['id']}/advance")
        # Feedback mẫu
        api("post", "/feedback", json={"source": "CUSTOMER", "category": "AUDIO", "title": "Khách góp ý nhạc nền to hơn lời thoại (DEMO)",
                                       "description": "Bình luận trên video Facebook", "project_id": p1["id"], "evidence_class": "FACT",
                                       "evidence": [{"type": "URL", "ref": "https://www.facebook.com/anhngan.demo/videos/1", "note": "Bình luận khách"}]})
    os.environ.pop("CELERY_TASK_ALWAYS_EAGER", None)
    print("Đã tạo dữ liệu mẫu DEMO")
