"""Tiện ích test: tạo file media hợp lệ bằng FFmpeg, đưa dự án qua từng bước workflow."""
import subprocess
import tempfile
import uuid
from pathlib import Path

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
OUT = Path(tempfile.mkdtemp(prefix="anngan_media_"))


def make_png(name="img.png", color="0x1E3A8A", size="400x400") -> Path:
    p = OUT / f"{uuid.uuid4().hex[:6]}_{name}"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", f"color=c={color}:s={size}", "-frames:v", "1", str(p)],
                   check=True)
    return p


def make_audio(name="a.mp3", seconds=3, freq=440) -> Path:
    p = OUT / f"{uuid.uuid4().hex[:6]}_{name}"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", f"sine=frequency={freq}:duration={seconds}", str(p)],
                   check=True)
    return p


def make_video(name="v.mp4", w=720, h=1280, seconds=8, audio=True) -> Path:
    p = OUT / f"{uuid.uuid4().hex[:6]}_{name}"
    cmd = ["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", f"testsrc=s={w}x{h}:d={seconds}:r=30"]
    if audio:
        cmd += ["-f", "lavfi", "-i", f"sine=frequency=500:duration={seconds}", "-c:a", "aac", "-shortest"]
    cmd += ["-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", str(p)]
    subprocess.run(cmd, check=True)
    return p


def upload(api, path: Path, asset_type: str, **form):
    with open(path, "rb") as f:
        r = api.post("/assets", files={"file": (path.name, f)}, data={"asset_type": asset_type, **form})
    return r


def create_project(api, channel_id, **kw):
    body = {"channel_id": channel_id, "topic": kw.pop("topic", "Chọn sữa phù hợp cho bé 2 tuổi"),
            "duration_sec": kw.pop("duration_sec", 16), "automation_level": kw.pop("automation_level", "ASSISTED"), **kw}
    r = api.post("/projects", json=body)
    assert r.status_code == 201, r.text
    return r.json()["projects"][0]


def to_storyboard(pm, project_id):
    r = pm.post(f"/projects/{project_id}/script/ideas")
    assert r.status_code == 200, r.text
    r = pm.post(f"/projects/{project_id}/script/write")
    assert r.status_code == 200, r.text
    r = pm.post(f"/projects/{project_id}/script/approve", json={"comment": "ok"})
    assert r.status_code == 200, r.text
    return r.json()


def to_scene_qc(pm, project_id):
    to_storyboard(pm, project_id)
    r = pm.post(f"/projects/{project_id}/validate-assets")
    assert r.status_code == 200, r.text
    assert not r.json()["blocking"], r.json()
    r = pm.post(f"/projects/{project_id}/generate", json={})
    assert r.status_code == 200, r.text
    return pm.get(f"/projects/{project_id}").json()


def full_scores(score=10, overrides=None):
    keys = ["hook", "script", "character", "setting", "visual", "voice", "lipsync", "audio", "brand", "compliance"]
    s = {k: {"score": score, "note": ""} for k in keys}
    for k, v in (overrides or {}).items():
        s[k] = {"score": v, "note": ""}
    return s
