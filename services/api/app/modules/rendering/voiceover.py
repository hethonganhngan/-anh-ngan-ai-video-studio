"""Tạo voice-over bằng TTS từ lời thoại các cảnh → 1 track âm thanh khớp mốc thời gian timeline (M06).

DEMO: Mock TTS (tiếng bíp, không tốn phí). PRODUCTION: provider TTS của Voice Profile (vd. Gemini TTS).
Mỗi cảnh: đọc từng câu theo giọng của người nói → nối liền trong cảnh → đặt tại mốc đầu cảnh, dài hơn cảnh thì tăng
tốc tối đa 1.25x (còn dài → cảnh báo). Clip AI có tiếng gốc (Flow tạo kèm tiếng để làm mốc, tiếng đó bị tắt khi dựng)
→ đặt giọng đúng lúc nhân vật mở miệng và co giãn 0.85–1.25x cho vừa khoảng khẩu hình.

Phân vai giọng: CHỈ nhân vật chính (Mẹ Ánh Ngân — giọng Voice Lock của dự án) bị khoá giọng. Mỗi người nói khác được
một giọng dựng sẵn riêng của provider (theo giới tính đoán từ cách xưng hô, ưu tiên giọng miền Nam), giữ nguyên giọng
đó xuyên suốt các cảnh. Nhân vật phụ đã có Voice Profile riêng thì dùng giọng đó.
"""
import re
import subprocess
import unicodedata
from decimal import Decimal

from app.core import audit
from app.core.config import get_settings
from app.core.context import Ctx
from app.core.errors import InvalidTransition, NotFound, ValidationFailed
from app.media.models import Asset
from app.media.service import ingest_file
from app.media.storage import get_storage, safe_remove
from app.modules.administration import service as admin
from app.modules.characters.models import Character, VoiceProfile
from app.modules.projects.service import lock_project
from app.modules.rendering.service import default_timeline, validate_timeline
from app.modules.scripts.models import Scene
from app.providers.tts.base import TTSError, TTSRequest
from app.providers.tts.registry import get_tts_provider
from app.workflows.jobs import tmp_path
from sqlalchemy import select

EDITABLE = ("SCENE_QC", "FINAL_QC", "RENDERING", "GENERATING", "NEEDS_MANUAL_ACTION", "APPROVAL_PENDING")
MAX_SPEEDUP = 1.25
MIN_TEMPO = 0.85  # giãn chậm tối đa khi khớp khẩu hình (chậm hơn nghe kéo giọng)
SPEECH_DB, SILENCE_MIN, MIN_WINDOW, MAX_COVER = -35, 0.3, 0.8, 0.9  # đo khoảng nói trên tiếng gốc clip
LINE_GAP = 0.15  # nghỉ giữa 2 câu thoại trong cùng cảnh (giây)
MAIN_NAME = "ánh ngân"
FEMALE_WORDS = {"mẹ", "má", "chị", "cô", "bà", "dì", "mợ", "thím", "vợ", "nữ"}
MALE_WORDS = {"ba", "bố", "cha", "tía", "anh", "chú", "ông", "bác", "cậu", "dượng", "chồng", "nam"}


def _norm(s: str | None) -> str:
    return " ".join(unicodedata.normalize("NFC", s or "").lower().split())


def _gender(label: str, char: Character | None) -> str:
    """female | male | "" — theo giới tính nhân vật nếu có, không thì theo từ xưng hô đầu tên ("Chị Hoa", "Anh Tuấn")."""
    g = _norm(char.gender) if char else ""
    if g in ("nữ", "female", "f"):
        return "female"
    if g in ("nam", "male", "m"):
        return "male"
    words = label.split()[:2]
    if words[:2] == ["bác", "sĩ"]:
        return ""
    for w in words:
        if w in FEMALE_WORDS:
            return "female"
        if w in MALE_WORDS:
            return "male"
    return ""


def _cast(ctx: Ctx, p, voice: VoiceProfile, provider, main_spec: dict, labels: list[str]) -> tuple[dict, list[str]]:
    """Gán giọng cho từng người nói (label đã chuẩn hoá) → {label: spec}. Chỉ nhân vật chính dùng giọng khoá."""
    chars = [c for c in (ctx.db.get(Character, cid) for cid in (p.character_ids or [])) if c and c.deleted_at is None]
    main = (next((c for c in chars if c.voice_profile_id == voice.id), None)
            or next((c for c in chars if MAIN_NAME in _norm(c.name)), None))
    main_names = [MAIN_NAME] + ([_norm(main.name)] if main else [])
    is_main = {lb: (not lb or any(n in lb for n in main_names)) for lb in labels}
    if labels and not any(is_main.values()):
        is_main[labels[0]] = True  # không ai khớp tên nhân vật chính → người nói đầu tiên giữ giọng khoá

    cast, warnings, used = {}, [], {main_spec["voice_id"]}
    options = None
    for lb in labels:
        if is_main[lb]:
            cast[lb] = main_spec
            continue
        char = next((c for c in chars if c is not main and _norm(c.name) and _norm(c.name) in lb), None)
        own = ctx.db.get(VoiceProfile, char.voice_profile_id) if char and char.voice_profile_id else None
        if (own and own.id != voice.id and own.deleted_at is None and own.consent_status != "REVOKED"
                and own.provider_code == voice.provider_code):
            ref = ctx.db.get(Asset, own.audio_reference_asset_id) if own.audio_reference_asset_id else None
            vid = own.provider_voice_id or (own.code if own.provider_code == "vieneu_local" else "")
            cast[lb] = {"voice_id": vid, "style": _style(own), "ref": get_storage().local_path(ref.storage_key) if ref else "",
                        "name": own.name}
            used.add(vid)
            continue
        if options is None:
            options = [o for o in provider.voice_options() if o.id != main_spec["voice_id"]]
        g = _gender(lb, char)
        pool = [o for o in options if not g or o.gender == g] or options
        free = [o for o in pool if o.id not in used] or pool
        if not free:
            warnings.append(f"Giọng {provider.code} không có giọng dựng sẵn — vai “{lb}” đọc chung giọng nhân vật chính")
            cast[lb] = main_spec
            continue
        pick = sorted(free, key=lambda o: o.region != "Nam")[0]  # ưu tiên giọng miền Nam như giọng chính
        used.add(pick.id)
        cast[lb] = {"voice_id": pick.id, "ref": "", "name": pick.id,
                    "style": "Đọc bằng tiếng Việt" + (f", giọng {voice.accent}" if voice.accent else "")}
    return cast, warnings


def _character_voice(ctx: Ctx, p) -> str | None:
    """Dự án chưa chọn giọng → dùng giọng gắn với nhân vật (Character Lock), nếu dự án chỉ có 1 nhân vật có giọng."""
    voices = {c.voice_profile_id for c in (ctx.db.get(Character, cid) for cid in (p.character_ids or [])) if c and c.voice_profile_id}
    return next(iter(voices)) if len(voices) == 1 else None


def _style(v: VoiceProfile) -> str:
    bits = [f"giọng {v.accent}" if v.accent else "", v.tone, f"tốc độ {v.speaking_rate}" if v.speaking_rate else ""]
    bits = [b for b in bits if b]
    return ("Đọc bằng tiếng Việt, " + ", ".join(bits)) if bits else ""


def speech_window(path: str, ts: float, te: float) -> tuple[float, float] | None:
    """Khoảng nhân vật nói trong clip (giây, tính từ trim_start) đo trên tiếng gốc của video AI.

    Flow tạo khẩu hình kèm tiếng nói theo nhịp riêng → giọng chính chủ được đặt & co giãn đúng khoảng này để khớp môi.
    Lọc dải tần giọng người rồi silencedetect; không có tiếng/khoảng quá ngắn → None (đặt ở đầu cảnh như cũ)."""
    dur = te - ts
    if dur <= 0:
        return None
    cmd = [get_settings().ffmpeg_bin, "-hide_banner", "-nostats", "-ss", f"{ts:.3f}", "-t", f"{dur:.3f}", "-i", path, "-vn",
           "-af", f"highpass=f=200,lowpass=f=3500,silencedetect=noise={SPEECH_DB}dB:d={SILENCE_MIN}", "-f", "null", "-"]
    try:
        err = subprocess.run(cmd, capture_output=True, text=True, timeout=120).stderr
    except (subprocess.SubprocessError, OSError):
        return None
    starts = [max(0.0, float(x)) for x in re.findall(r"silence_start: (-?[\d.]+)", err)]
    ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", err)]
    silences = [(s0, ends[i] if i < len(ends) else dur) for i, s0 in enumerate(starts)]
    voiced, cur = [], 0.0
    for s0, s1 in silences:
        if s0 - cur >= 0.15:
            voiced.append((cur, s0))
        cur = max(cur, s1)
    if dur - cur >= 0.15:
        voiced.append((cur, dur))
    if not voiced or voiced[-1][1] - voiced[0][0] < MIN_WINDOW:
        return None
    if voiced[-1][1] - voiced[0][0] > MAX_COVER * dur:  # gần kín cả clip = nhạc nền/tiếng ồn, không phải lời nói
        return None
    return round(voiced[0][0], 3), round(voiced[-1][1], 3)


def _segments(ctx: Ctx, tl: dict) -> tuple[list[dict], float]:
    """Mốc bắt đầu + thời lượng từng clip có lời thoại (kèm khoảng khẩu hình nếu đo được), và tổng thời lượng."""
    out, t = [], 0.0
    for c in tl.get("clips") or []:
        a = ctx.db.get(Asset, c["asset_id"]) if c.get("asset_id") else None
        scene = ctx.db.get(Scene, c["scene_id"])
        ts = float(c.get("trim_start") or 0)
        te = float(c["trim_end"]) if c.get("trim_end") is not None else float((a.duration_sec if a else 0) or 0)
        dur = max(0.0, te - ts)
        lines = [{"speaker": _norm(d.get("speaker")), "text": (d.get("text") or "").strip()}
                 for d in (scene.dialogue or []) if isinstance(d, dict)]
        lines = [ln for ln in lines if ln["text"]]
        if lines:
            win = (speech_window(get_storage().local_path(a.storage_key), ts, te)
                   if a and (a.media_info or {}).get("has_audio") else None)
            out.append({"scene_id": str(scene.id), "order": scene.order_index + 1, "start": round(t, 3),
                        "slot": round(dur, 3), "text": " ".join(ln["text"] for ln in lines), "lines": lines,
                        "window": win})
        t += dur
    return out, round(t, 3)


def generate_voiceover(ctx: Ctx, project_id, *, voice_profile_id=None, scene_volume: float = 0.35,
                       actor_check: bool = True) -> dict:
    if actor_check:  # pipeline AUTO (worker) gọi với actor_check=False, giống start_render
        ctx.require("editor.edit")
    p = lock_project(ctx, project_id)
    if p.status not in EDITABLE:
        raise InvalidTransition(f"Không tạo voice-over ở trạng thái {p.status}")
    tl = dict(p.timeline) if p.timeline else default_timeline(ctx, p)
    validate_timeline(ctx, p, tl)
    vid = voice_profile_id or p.voice_profile_id or _character_voice(ctx, p)
    voice = ctx.db.get(VoiceProfile, vid) if vid else None
    if voice is None or voice.deleted_at is not None or voice.data_mode != ctx.mode:
        raise NotFound("Dự án chưa chọn Voice Profile")
    if voice.consent_status == "REVOKED":
        raise ValidationFailed("Voice Profile đã bị thu hồi quyền sử dụng", code="VOICE_CONSENT_REVOKED")
    segs, timeline_len = _segments(ctx, tl)
    if not segs:
        raise ValidationFailed("Các cảnh trên timeline chưa có lời thoại", code="NO_DIALOGUE")

    provider = get_tts_provider(ctx.db, voice.provider_code, ctx.mode)
    ref = ctx.db.get(Asset, voice.audio_reference_asset_id) if voice.audio_reference_asset_id else None
    ref_path = get_storage().local_path(ref.storage_key) if ref else ""  # bản ghi chính chủ → giọng nhân bản
    voice_id = voice.provider_voice_id or (voice.code if voice.provider_code == "vieneu_local" else "")
    estimated = Decimal(str(sum(provider.estimate_cost_vnd(s["text"]) for s in segs)))
    admin.check_budget(ctx, estimated=estimated, project=p, provider_code=provider.code)

    s = get_settings()
    cleanup, warnings, total_sec = [], [], 0.0
    try:
        for seg in segs:
            try:
                r = provider.synthesize(TTSRequest(text=seg["text"], voice_id=voice_id, style=_style(voice),
                                                   reference_audio_path=ref_path))
            except TTSError as e:
                raise ValidationFailed(f"Cảnh {seg['order']}: tạo giọng đọc lỗi — {e}", code=e.code)
            cleanup.append(r.path)
            seg["path"], seg["duration"] = r.path, r.duration_sec
            total_sec += r.duration_sec
            win = seg.pop("window")
            if win:  # khớp môi: bắt đầu khi nhân vật mở miệng, co giãn cho vừa khoảng nói (giữ cao độ)
                w0, w1 = win
                seg["start"] = round(seg["start"] + w0, 3)
                seg["tempo"] = round(min(MAX_SPEEDUP, max(MIN_TEMPO, r.duration_sec / (w1 - w0))), 3)
                seg["slot"] = round(seg["slot"] - w0, 3)
                seg["lip_window"] = [w0, w1]
            else:
                slot = max(0.5, seg["slot"] - 0.2)
                seg["tempo"] = round(min(MAX_SPEEDUP, r.duration_sec / slot), 3) if r.duration_sec > slot else 1.0
                seg["lip_window"] = None
            if r.duration_sec / seg["tempo"] > seg["slot"] + 0.05:
                warnings.append(f"Cảnh {seg['order']}: lời thoại {r.duration_sec:.1f}s dài hơn cảnh {seg['slot']:.1f}s "
                                "— nên rút gọn thoại")
        total = max(timeline_len, max(x["start"] + x["duration"] / x["tempo"] for x in segs))
        out = tmp_path(".m4a")
        cleanup.append(out)
        cmd = [s.ffmpeg_bin, "-y", "-hide_banner", "-loglevel", "error"]
        fc = []
        for i, seg in enumerate(segs):
            cmd += ["-i", seg["path"]]
            tempo = f"atempo={seg['tempo']}," if seg["tempo"] != 1.0 else ""
            fc.append(f"[{i}:a]aresample=48000,{tempo}adelay={int(seg['start'] * 1000)}:all=1[v{i}]")
        fc.append("".join(f"[v{i}]" for i in range(len(segs))) +
                  f"amix=inputs={len(segs)}:normalize=0:dropout_transition=0,apad,atrim=0:{total:.3f}[out]")
        cmd += ["-filter_complex", ";".join(fc), "-map", "[out]", "-ac", "2", "-c:a", "aac", "-b:a", "160k", out]
        subprocess.run(cmd, check=True, timeout=300)

        asset = ingest_file(ctx, out, f"voiceover_{p.code}.m4a", asset_type="AUDIO", name=f"Voice-over {p.code} ({voice.name})",
                            source="API_PROVIDER" if provider.is_real else "MOCK_PROVIDER",
                            usage_rights="AI_GENERATED" if provider.is_real else "OWNED", tags=["voiceover", "tts"],
                            project_id=p.id, channel_id=p.channel_id,
                            extra_info={"tts_provider": provider.code, "voice_profile": voice.code,
                                        "voice_id": voice.provider_voice_id, "simulated": not provider.is_real})
    finally:
        for f in cleanup:
            safe_remove(f)

    cost = Decimal(str(round(total_sec * float(provider.unit_cost_vnd_per_sec), 2)))
    admin.record_cost(ctx.db, ctx.mode, category="TTS", provider_code=provider.code, amount=cost,
                      quantity=Decimal(str(round(total_sec, 2))), unit="SECOND", project=p, is_simulated=not provider.is_real,
                      description=f"Voice-over {p.code} · {len(segs)} cảnh")

    old_tts = {str(a.id) for a in ctx.db.scalars(select(Asset).where(Asset.project_id == p.id)).all() if "tts" in (a.tags or [])}
    tl["voiceover"] = [v for v in (tl.get("voiceover") or []) if str(v["asset_id"]) not in old_tts and str(v["asset_id"]) != str(asset.id)]
    tl["voiceover"] = (tl["voiceover"] + [{"asset_id": str(asset.id), "start": 0.0, "volume": 1.0}])[-5:]
    tl["clips"] = [{**c, "volume": scene_volume} for c in tl["clips"]]
    validate_timeline(ctx, p, tl)
    p.timeline = tl
    audit.record(ctx, "editor.voiceover_generate", "project", p.id,
                 after={"asset": str(asset.id), "provider": provider.code, "segments": len(segs), "seconds": round(total_sec, 1)})
    return {"timeline": tl, "asset_id": str(asset.id), "provider": provider.code, "simulated": not provider.is_real,
            "duration_sec": round(total_sec, 2), "cost_vnd": float(cost), "warnings": warnings,
            "segments": [{k: seg[k] for k in ("order", "start", "slot", "duration", "tempo", "text", "lip_window")}
                         for seg in segs]}
