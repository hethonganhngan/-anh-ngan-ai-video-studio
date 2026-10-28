"""FFprobe: đọc & kiểm tra metadata media."""
import json
import subprocess

from app.core.config import get_settings
from app.core.errors import ValidationFailed


def ffprobe(path: str) -> dict:
    s = get_settings()
    try:
        out = subprocess.run(
            [s.ffprobe_bin, "-v", "error", "-print_format", "json", "-show_format", "-show_streams", path],
            capture_output=True, text=True, timeout=60, check=True,
        )
    except subprocess.CalledProcessError as e:
        raise ValidationFailed("File media hỏng hoặc không đọc được", code="INVALID_MEDIA", details=e.stderr[-500:])
    except subprocess.TimeoutExpired:
        raise ValidationFailed("Đọc metadata quá thời gian", code="INVALID_MEDIA")
    return json.loads(out.stdout or "{}")


def summarize(probe: dict) -> dict:
    streams = probe.get("streams", [])
    v = next((s for s in streams if s.get("codec_type") == "video"), None)
    a = next((s for s in streams if s.get("codec_type") == "audio"), None)
    fmt = probe.get("format", {})
    dur = fmt.get("duration") or (v or {}).get("duration")
    fps = None
    if v and v.get("avg_frame_rate") and v["avg_frame_rate"] != "0/0":
        n, d = v["avg_frame_rate"].split("/")
        fps = round(float(n) / float(d), 2) if float(d) else None
    return {
        "format_name": fmt.get("format_name"),
        "duration_sec": round(float(dur), 3) if dur else None,
        "width": int(v["width"]) if v and v.get("width") else None,
        "height": int(v["height"]) if v and v.get("height") else None,
        "video_codec": v.get("codec_name") if v else None,
        "fps": fps,
        "has_audio": a is not None,
        "audio_codec": a.get("codec_name") if a else None,
        "bit_rate": int(fmt["bit_rate"]) if fmt.get("bit_rate") else None,
    }
