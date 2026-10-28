"""MockVideoProvider — tạo MP4 THẬT bằng FFmpeg (khung màu + chữ + âm thanh) để chạy thử toàn bộ pipeline.

Đây KHÔNG phải kết nối AI thật. Chi phí là mô phỏng. Hỗ trợ tiêm lỗi để kiểm thử:
  [[MOCK_FAIL]]       → luôn thất bại
  [[MOCK_FAIL_ONCE]]  → thất bại ở lần thử đầu, thành công khi retry
  [[MOCK_TIMEOUT]]    → mô phỏng timeout của nhà cung cấp
  [[MOCK_UNAVAILABLE]]→ nhà cung cấp không khả dụng
"""
import hashlib
import json
import os
import subprocess
import tempfile
from decimal import Decimal
from pathlib import Path

from app.core.config import get_settings
from app.providers.video.base import GenerationSpec, ProviderError, ProviderStatus, VideoProvider

PALETTE = ["0x1E3A8A", "0x0F766E", "0x7C2D12", "0x4C1D95", "0x065F46", "0x9D174D", "0x1E40AF", "0x854D0E"]


def _work_dir() -> Path:
    d = Path(get_settings().storage_local_root).parent / "provider_work" / "mock"
    d.mkdir(parents=True, exist_ok=True)
    return d


class MockVideoProvider(VideoProvider):
    code = "mock"
    name = "Mock Video Provider (DEMO)"
    kind = "MOCK"
    is_real = False
    unit_cost_vnd_per_sec = Decimal(1500)  # mô phỏng để kiểm thử ngân sách
    max_duration_sec = 10
    supported_aspects = ("9:16", "16:9", "1:1")

    def _state_path(self, job_id: str) -> Path:
        return _work_dir() / f"{job_id}.json"

    def submit_generation(self, spec: GenerationSpec) -> str:
        p = spec.prompt_text
        if "[[MOCK_UNAVAILABLE]]" in p:
            raise ProviderError("Mock provider tạm không khả dụng", code="PROVIDER_UNAVAILABLE", retryable=True)
        if "[[MOCK_TIMEOUT]]" in p:
            raise ProviderError("Mock provider hết thời gian chờ", code="TIMEOUT", retryable=True)
        job_id = "mock-" + hashlib.sha1(f"{spec.job_ref}:{spec.attempt_no}".encode()).hexdigest()[:16]
        state = {"state": "RUNNING", "spec": spec.__dict__}
        if "[[MOCK_FAIL]]" in p or ("[[MOCK_FAIL_ONCE]]" in p and spec.attempt_no == 1):
            state = {"state": "FAILED", "error_code": "GENERATION_FAILED",
                     "error_message": "Mock: nhà cung cấp trả lỗi tạo video (tiêm lỗi)"}
        else:
            out = _work_dir() / f"{job_id}.mp4"
            self._render(spec, str(out))
            state = {"state": "SUCCEEDED", "file": str(out)}
        self._state_path(job_id).write_text(json.dumps(state, ensure_ascii=False, default=str))
        return job_id

    def _render(self, spec: GenerationSpec, out: str) -> None:
        s = get_settings()
        w, h = (s.mock_video_width, s.mock_video_height) if spec.aspect_ratio == "9:16" else (spec.width, spec.height)
        color = PALETTE[int(hashlib.md5(spec.job_ref.encode()).hexdigest(), 16) % len(PALETTE)]
        lines = [d.get("text", "") if isinstance(d, dict) else str(d) for d in (spec.dialogue or [])][:2]
        title = (spec.scene_title or "Cảnh")[:60]
        fs_title, fs_body = max(18, w // 18), max(14, w // 30)
        with tempfile.TemporaryDirectory() as td:
            t1 = os.path.join(td, "t1.txt")
            t2 = os.path.join(td, "t2.txt")
            t3 = os.path.join(td, "t3.txt")
            Path(t1).write_text(title, encoding="utf-8")
            Path(t2).write_text("\n".join(_wrap(x, 28) for x in lines) or " ", encoding="utf-8")
            Path(t3).write_text("DEMO · MOCK PROVIDER", encoding="utf-8")
            font = s.font_file
            vf = (
                f"drawtext=fontfile={font}:textfile={t3}:fontcolor=white@0.7:fontsize={fs_body}:x=(w-tw)/2:y=h*0.06,"
                f"drawtext=fontfile={font}:textfile={t1}:fontcolor=white:fontsize={fs_title}:x=(w-tw)/2:y=h*0.35,"
                f"drawtext=fontfile={font}:textfile={t2}:fontcolor=white:fontsize={fs_body}:line_spacing=12:x=(w-tw)/2:y=h*0.5,"
                f"drawbox=x=0:y=ih-ih/40:w=iw*t/{spec.duration_sec}:h=ih/40:color=white@0.8:t=fill"
            )
            freq = 220 + int(hashlib.md5(spec.job_ref.encode()).hexdigest()[:2], 16)
            cmd = [
                s.ffmpeg_bin, "-y", "-hide_banner", "-loglevel", "error",
                "-f", "lavfi", "-i", f"color=c={color}:s={w}x{h}:d={spec.duration_sec}:r={s.output_fps}",
                "-f", "lavfi", "-i", f"sine=frequency={freq}:sample_rate=48000:duration={spec.duration_sec}",
                "-vf", vf, "-af", "volume=0.08", "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "96k", "-shortest", "-movflags", "+faststart", out,
            ]
            try:
                subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=180)
            except subprocess.CalledProcessError as e:
                raise ProviderError(f"Mock FFmpeg lỗi: {e.stderr[-300:]}", code="MOCK_RENDER_FAILED", retryable=False)

    def _load(self, job_id: str) -> dict:
        p = self._state_path(job_id)
        if not p.exists():
            raise ProviderError("Không tìm thấy tác vụ mock", code="NOT_FOUND", retryable=False)
        return json.loads(p.read_text())

    def get_status(self, provider_job_id):
        st = self._load(provider_job_id)
        return ProviderStatus(state=st["state"], progress=100 if st["state"] == "SUCCEEDED" else 0,
                              error_code=st.get("error_code"), error_message=st.get("error_message"))

    def get_result(self, provider_job_id):
        st = self._load(provider_job_id)
        if st["state"] != "SUCCEEDED":
            raise ProviderError("Tác vụ chưa có kết quả", code="NOT_READY", retryable=True)
        return st["file"]

    def cancel_job(self, provider_job_id):
        p = self._state_path(provider_job_id)
        if p.exists():
            st = json.loads(p.read_text())
            if st["state"] in ("RUNNING", "SUBMITTED"):
                st["state"] = "CANCELLED"
                p.write_text(json.dumps(st))
        return True


def _wrap(text: str, width: int) -> str:
    words, lines, cur = text.split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 > width:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        lines.append(cur)
    return "\n".join(lines)
