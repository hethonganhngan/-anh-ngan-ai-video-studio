"""Khớp môi (D25): đo khoảng nhân vật nói trên tiếng gốc clip Flow để đặt giọng chính chủ đúng lúc mở miệng."""
import subprocess

from app.core.config import get_settings
from app.modules.rendering.voiceover import speech_window


def _wav(path, filt):
    subprocess.run([get_settings().ffmpeg_bin, "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i", filt,
                    "-t", "8", "-ac", "1", "-ar", "24000", str(path)], check=True)


def test_window_from_lead_and_tail_silence(tmp_path):
    f = tmp_path / "a.wav"  # 1.2 s lặng → 3.5 s "nói" (440 Hz) → lặng đến hết
    _wav(f, "aevalsrc='if(between(t,1.2,4.7),0.5*sin(2*PI*440*t),0)':s=24000")
    w0, w1 = speech_window(str(f), 0.0, 8.0)
    assert abs(w0 - 1.2) < 0.1 and abs(w1 - 4.7) < 0.1
    w0, w1 = speech_window(str(f), 0.5, 8.0)  # tính từ trim_start
    assert abs(w0 - 0.7) < 0.1 and abs(w1 - 4.2) < 0.1


def test_no_speech_or_full_clip_noise_is_ignored(tmp_path):
    silent, music = tmp_path / "s.wav", tmp_path / "m.wav"
    _wav(silent, "anullsrc=r=24000:cl=mono")
    _wav(music, "sine=frequency=500:sample_rate=24000")
    assert speech_window(str(silent), 0.0, 8.0) is None
    assert speech_window(str(music), 0.0, 8.0) is None  # kín cả clip = nhạc nền, không căn theo
