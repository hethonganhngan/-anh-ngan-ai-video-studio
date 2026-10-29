"""Tạo voice-over bằng TTS từ lời thoại các cảnh → 1 track âm thanh khớp mốc thời gian timeline (M06).

DEMO: Mock TTS (tiếng bíp, không tốn phí). PRODUCTION: provider TTS của Voice Profile (vd. Gemini TTS).
Mỗi cảnh: ghép thoại → đọc → nếu dài hơn cảnh thì tăng tốc tối đa 1.25x (còn dài → cảnh báo) → đặt tại mốc đầu cảnh.
"""
import subprocess
from decimal import Decimal

from app.core import audit
from app.core.config import get_settings
from app.core.context import Ctx
from app.core.errors import InvalidTransition, NotFound, ValidationFailed
from app.media.models import Asset
from app.media.service import ingest_file
from app.media.storage import safe_remove
from app.modules.administration import service as admin
from app.modules.characters.models import VoiceProfile
from app.modules.projects.service import lock_project
from app.modules.rendering.service import default_timeline, validate_timeline
from app.modules.scripts.models import Scene
from app.providers.tts.base import TTSError, TTSRequest
from app.providers.tts.registry import get_tts_provider
from app.workflows.jobs import tmp_path
from sqlalchemy import select

EDITABLE = ("SCENE_QC", "FINAL_QC", "RENDERING", "GENERATING", "NEEDS_MANUAL_ACTION", "APPROVAL_PENDING")
MAX_SPEEDUP = 1.25


def _style(v: VoiceProfile) -> str:
    bits = [f"giọng {v.accent}" if v.accent else "", v.tone, f"tốc độ {v.speaking_rate}" if v.speaking_rate else ""]
    bits = [b for b in bits if b]
    return ("Đọc bằng tiếng Việt, " + ", ".join(bits)) if bits else ""


def _segments(ctx: Ctx, tl: dict) -> tuple[list[dict], float]:
    """Mốc bắt đầu + thời lượng từng clip có lời thoại, và tổng thời lượng timeline."""
    out, t = [], 0.0
    for c in tl.get("clips") or []:
        a = ctx.db.get(Asset, c["asset_id"]) if c.get("asset_id") else None
        scene = ctx.db.get(Scene, c["scene_id"])
        ts = float(c.get("trim_start") or 0)
        te = float(c["trim_end"]) if c.get("trim_end") is not None else float((a.duration_sec if a else 0) or 0)
        dur = max(0.0, te - ts)
        text = " ".join((d.get("text") or "").strip() for d in (scene.dialogue or []) if isinstance(d, dict)).strip()
        if text:
            out.append({"scene_id": str(scene.id), "order": scene.order_index + 1, "start": round(t, 3),
                        "slot": round(dur, 3), "text": text})
        t += dur
    return out, round(t, 3)


def generate_voiceover(ctx: Ctx, project_id, *, voice_profile_id=None, scene_volume: float = 0.35) -> dict:
    ctx.require("editor.edit")
    p = lock_project(ctx, project_id)
    if p.status not in EDITABLE:
        raise InvalidTransition(f"Không tạo voice-over ở trạng thái {p.status}")
    tl = dict(p.timeline) if p.timeline else default_timeline(ctx, p)
    validate_timeline(ctx, p, tl)
    vid = voice_profile_id or p.voice_profile_id
    voice = ctx.db.get(VoiceProfile, vid) if vid else None
    if voice is None or voice.deleted_at is not None or voice.data_mode != ctx.mode:
        raise NotFound("Dự án chưa chọn Voice Profile")
    if voice.consent_status == "REVOKED":
        raise ValidationFailed("Voice Profile đã bị thu hồi quyền sử dụng", code="VOICE_CONSENT_REVOKED")
    segs, timeline_len = _segments(ctx, tl)
    if not segs:
        raise ValidationFailed("Các cảnh trên timeline chưa có lời thoại", code="NO_DIALOGUE")

    provider = get_tts_provider(ctx.db, voice.provider_code, ctx.mode)
    estimated = Decimal(str(sum(provider.estimate_cost_vnd(s["text"]) for s in segs)))
    admin.check_budget(ctx, estimated=estimated, project=p, provider_code=provider.code)

    s = get_settings()
    cleanup, warnings, total_sec = [], [], 0.0
    try:
        for seg in segs:
            try:
                r = provider.synthesize(TTSRequest(text=seg["text"], voice_id=voice.provider_voice_id or "", style=_style(voice)))
            except TTSError as e:
                raise ValidationFailed(f"Cảnh {seg['order']}: tạo giọng đọc lỗi — {e}", code=e.code)
            cleanup.append(r.path)
            seg["path"], seg["duration"] = r.path, r.duration_sec
            total_sec += r.duration_sec
            slot = max(0.5, seg["slot"] - 0.2)
            seg["tempo"] = round(min(MAX_SPEEDUP, r.duration_sec / slot), 3) if r.duration_sec > slot else 1.0
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
            "segments": [{k: seg[k] for k in ("order", "start", "slot", "duration", "tempo", "text")} for seg in segs]}
