"""FFmpeg Render Engine — dựng video thật từ timeline.

Pipeline (1 lệnh filter_complex):
  clip_i → trim → scale/pad 1080x1920 → fps 30 → concat
  → (tuỳ chọn) burn phụ đề SRT (libass) → (tuỳ chọn) overlay logo
  audio: âm thanh cảnh (hoặc im lặng) concat + voice-over (adelay) + nhạc nền (loop, volume, fade) → amix → loudnorm
"""
import json
import os
import re
import subprocess
from dataclasses import dataclass, field

from app.core.config import get_settings


class RenderError(Exception):
    pass


@dataclass
class ClipIn:
    path: str
    duration: float
    has_audio: bool
    trim_start: float = 0.0
    trim_end: float | None = None
    dialogue: list = field(default_factory=list)
    volume: float = 1.0

    @property
    def length(self) -> float:
        end = self.trim_end if self.trim_end is not None else self.duration
        return max(0.1, min(end, self.duration) - self.trim_start)


@dataclass
class AudioIn:
    path: str
    start: float = 0.0
    volume: float = 1.0


@dataclass
class RenderPlan:
    clips: list[ClipIn]
    output: str
    srt_path: str | None = None
    burn_subtitles: bool = True
    subtitle_font_size: int = 10
    logo_path: str | None = None
    logo_position: str = "top_right"
    logo_scale: float = 0.18
    logo_opacity: float = 0.9
    voiceovers: list[AudioIn] = field(default_factory=list)
    music: AudioIn | None = None
    music_fade_out: float = 2.0
    loudnorm: bool = True
    width: int = 1080
    height: int = 1920
    fps: int = 30


def _fmt_ts(t: float) -> str:
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def build_srt(clips: list[ClipIn]) -> str:
    """Phụ đề từ lời thoại: mỗi cảnh chia đều thời lượng cho các câu thoại."""
    entries, t, idx = [], 0.0, 1
    for c in clips:
        lines = [d.get("text", "") if isinstance(d, dict) else str(d) for d in (c.dialogue or []) if d]
        lines = [x for x in lines if x.strip()]
        if lines:
            slot = c.length / len(lines)
            for i, text in enumerate(lines):
                start = t + i * slot + 0.15
                end = t + (i + 1) * slot - 0.15
                entries.append(f"{idx}\n{_fmt_ts(start)} --> {_fmt_ts(max(start + 0.5, end))}\n{_wrap(text)}\n")
                idx += 1
        t += c.length
    return "\n".join(entries)


def _wrap(text: str, width: int = 32) -> str:
    words, lines, cur = text.split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 > width and cur:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        lines.append(cur)
    return "\n".join(lines[:3])


def _esc_filter_path(p: str) -> str:
    return p.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'").replace(",", "\\,")


def filter_path(p) -> str:
    """Đường dẫn làm giá trị tuỳ chọn filter (fontfile, textfile): dùng '/', thoát ':' (ổ đĩa Windows), bọc nháy."""
    return "'" + str(p).replace("\\", "/").replace(":", "\\:") + "'"


def build_command(plan: RenderPlan) -> list[str]:
    s = get_settings()
    if not plan.clips:
        raise RenderError("Timeline không có cảnh nào")
    W, H, FPS = plan.width, plan.height, plan.fps
    cmd = [s.ffmpeg_bin, "-y", "-hide_banner", "-loglevel", "error"]
    for c in plan.clips:
        cmd += ["-ss", f"{c.trim_start:.3f}", "-t", f"{c.length:.3f}", "-i", c.path]
    n = len(plan.clips)
    idx = n
    vo_idx = []
    for vo in plan.voiceovers:
        cmd += ["-i", vo.path]
        vo_idx.append(idx)
        idx += 1
    music_idx = None
    if plan.music:
        cmd += ["-stream_loop", "-1", "-i", plan.music.path]
        music_idx = idx
        idx += 1
    logo_idx = None
    if plan.logo_path:
        cmd += ["-i", plan.logo_path]
        logo_idx = idx
        idx += 1
    total = sum(c.length for c in plan.clips)
    fc = []
    concat_in = ""
    for i, c in enumerate(plan.clips):
        fc.append(f"[{i}:v]scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color=black,"
                  f"setsar=1,fps={FPS},format=yuv420p,trim=duration={c.length:.3f},setpts=PTS-STARTPTS[v{i}]")
        if c.has_audio:
            fc.append(f"[{i}:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,volume={c.volume:.2f},"
                      f"atrim=duration={c.length:.3f},apad=whole_dur={c.length:.3f},asetpts=PTS-STARTPTS[a{i}]")
        else:
            fc.append(f"anullsrc=r=48000:cl=stereo,atrim=duration={c.length:.3f},aformat=sample_fmts=fltp:channel_layouts=stereo[a{i}]")
        concat_in += f"[v{i}][a{i}]"
    fc.append(f"{concat_in}concat=n={n}:v=1:a=1[vc][ac]")
    vlabel = "vc"
    if plan.srt_path and plan.burn_subtitles:
        style = (f"FontName=DejaVu Sans,Fontsize={plan.subtitle_font_size},PrimaryColour=&H00FFFFFF,OutlineColour=&H80000000,"
                 "BorderStyle=1,Outline=1.5,Shadow=0,Alignment=2,MarginV=28")
        fc.append(f"[{vlabel}]subtitles='{_esc_filter_path(plan.srt_path)}':original_size={W}x{H}:force_style='{style}'[vs]")
        vlabel = "vs"
    if logo_idx is not None:
        lw = int(W * plan.logo_scale)
        pos = {"top_right": "W-w-40:40", "top_left": "40:40", "bottom_right": "W-w-40:H-h-220",
               "bottom_left": "40:H-h-220"}.get(plan.logo_position, "W-w-40:40")
        fc.append(f"[{logo_idx}:v]scale={lw}:-1,format=rgba,colorchannelmixer=aa={plan.logo_opacity:.2f}[lg]")
        fc.append(f"[{vlabel}][lg]overlay={pos}:format=auto[vl]")
        vlabel = "vl"
    mix = ["[ac]"]
    for j, vo in zip(vo_idx, plan.voiceovers, strict=False):
        delay = int(vo.start * 1000)
        fc.append(f"[{j}:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,volume={vo.volume:.2f},"
                  f"adelay={delay}|{delay}[vo{j}]")
        mix.append(f"[vo{j}]")
    if music_idx is not None:
        fade_st = max(0.0, total - plan.music_fade_out)
        fc.append(f"[{music_idx}:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,"
                  f"volume={plan.music.volume:.2f},atrim=duration={total:.3f},afade=t=out:st={fade_st:.3f}:d={plan.music_fade_out:.2f}[bgm]")
        mix.append("[bgm]")
    if len(mix) > 1:
        fc.append(f"{''.join(mix)}amix=inputs={len(mix)}:duration=first:dropout_transition=0:normalize=0[am]")
        alabel = "am"
    else:
        alabel = "ac"
    if plan.loudnorm:
        fc.append(f"[{alabel}]loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000[aout]")
        alabel = "aout"
    cmd += ["-filter_complex", ";".join(fc), "-map", f"[{vlabel}]", "-map", f"[{alabel}]",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-r", str(FPS),
            "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-t", f"{total:.3f}", "-movflags", "+faststart", plan.output]
    return cmd


def run(cmd: list[str], timeout: int = 1800) -> None:
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=timeout)
    except subprocess.CalledProcessError as e:
        raise RenderError(f"FFmpeg lỗi: {(e.stderr or '')[-800:]}")
    except subprocess.TimeoutExpired:
        raise RenderError("FFmpeg quá thời gian render")


def render(plan: RenderPlan) -> None:
    if plan.srt_path is None and any(c.dialogue for c in plan.clips):
        raise RenderError("Thiếu file phụ đề")
    run(build_command(plan))
    if not os.path.exists(plan.output) or os.path.getsize(plan.output) == 0:
        raise RenderError("FFmpeg không tạo được file đầu ra")


def make_thumbnail(video: str, out_jpg: str, time_sec: float = 1.0, title: str | None = None) -> None:
    s = get_settings()
    vf = "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2"
    tmp_txt = None
    if title:
        tmp_txt = out_jpg + ".txt"
        with open(tmp_txt, "w", encoding="utf-8") as f:
            f.write(_wrap(title, 22))
        vf += (f",drawbox=x=0:y=ih*0.70:w=iw:h=ih*0.18:color=black@0.55:t=fill,"
               f"drawtext=fontfile={filter_path(s.font_file)}:textfile={filter_path(tmp_txt)}:fontcolor=white:fontsize=64:line_spacing=14:"
               f"x=(w-tw)/2:y=h*0.72")
    try:
        run([s.ffmpeg_bin, "-y", "-hide_banner", "-loglevel", "error", "-ss", f"{time_sec:.2f}", "-i", video,
             "-frames:v", "1", "-vf", vf, "-q:v", "3", out_jpg], timeout=120)
    finally:
        if tmp_txt and os.path.exists(tmp_txt):
            os.remove(tmp_txt)


# ---------- Đo đạc phục vụ QC tự động ----------
def measure(video: str) -> dict:
    """Đo độ ồn (EBU R128), khung đen, khoảng lặng."""
    s = get_settings()
    out: dict = {}
    r = subprocess.run([s.ffmpeg_bin, "-hide_banner", "-nostats", "-i", video, "-af", "ebur128=peak=true", "-f", "null", "-"],
                       capture_output=True, text=True, timeout=600)
    m = re.findall(r"I:\s+(-?[\d.]+) LUFS", r.stderr)
    out["integrated_lufs"] = float(m[-1]) if m else None
    tp = re.findall(r"Peak:\s+(-?[\d.]+) dBFS", r.stderr)
    out["true_peak_dbfs"] = float(tp[-1]) if tp else None
    r = subprocess.run([s.ffmpeg_bin, "-hide_banner", "-nostats", "-i", video, "-vf", "blackdetect=d=0.3:pix_th=0.08",
                        "-an", "-f", "null", "-"], capture_output=True, text=True, timeout=600)
    black = [float(x) for x in re.findall(r"black_duration:([\d.]+)", r.stderr)]
    out["black_seconds"] = round(sum(black), 2)
    out["black_segments"] = len(black)
    r = subprocess.run([s.ffmpeg_bin, "-hide_banner", "-nostats", "-i", video, "-af", "silencedetect=n=-45dB:d=2",
                        "-vn", "-f", "null", "-"], capture_output=True, text=True, timeout=600)
    sil = [float(x) for x in re.findall(r"silence_duration: ([\d.]+)", r.stderr)]
    out["silence_seconds"] = round(sum(sil), 2)
    out["longest_silence"] = max(sil) if sil else 0.0
    return out


def plan_to_json(plan: RenderPlan) -> str:
    return json.dumps({"clips": [c.__dict__ for c in plan.clips], "srt": plan.srt_path, "logo": plan.logo_path}, ensure_ascii=False)
