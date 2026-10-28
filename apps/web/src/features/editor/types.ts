export type Clip = { scene_id: string; asset_id: string | null; trim_start: number; trim_end: number | null; volume: number };
export type AudioTrack = { asset_id: string; start: number; volume: number };
export type Timeline = {
  clips: Clip[];
  subtitles: { enabled: boolean; burn_in: boolean; font_size: number };
  voiceover: AudioTrack[];
  music: { asset_id: string; volume: number; fade_out: number } | null;
  logo: { asset_id: string; position: string; scale: number; opacity: number } | null;
  thumbnail: { time_sec: number; title: string | null };
};
export type RenderOut = {
  id: string; version_no: number; video_asset_id: string; thumbnail_asset_id: string | null; subtitle_asset_id: string | null;
  duration_sec: number; width: number; height: number; size_bytes: number; status: string; created_at: string;
};
export type RenderJob = { id: string; project_id: string; status: string; attempt_no: number; max_retries: number; error_message: string | null; log: { msg: string; at?: string }[]; created_at: string; finished_at: string | null };

export function normalize(t: Partial<Timeline>): Timeline {
  return {
    clips: (t.clips ?? []).map((c) => ({ scene_id: c.scene_id, asset_id: c.asset_id ?? null, trim_start: Number(c.trim_start ?? 0), trim_end: c.trim_end ?? null, volume: Number(c.volume ?? 1) })),
    subtitles: { enabled: t.subtitles?.enabled ?? true, burn_in: t.subtitles?.burn_in ?? true, font_size: t.subtitles?.font_size ?? 10 },
    voiceover: (t.voiceover ?? []).map((v) => ({ asset_id: v.asset_id, start: Number(v.start ?? 0), volume: Number(v.volume ?? 1) })),
    music: t.music ? { asset_id: t.music.asset_id, volume: Number(t.music.volume ?? 0.15), fade_out: Number(t.music.fade_out ?? 2) } : null,
    logo: t.logo ? { asset_id: t.logo.asset_id, position: t.logo.position ?? "top_right", scale: Number(t.logo.scale ?? 0.18), opacity: Number(t.logo.opacity ?? 0.9) } : null,
    thumbnail: { time_sec: Number(t.thumbnail?.time_sec ?? 1), title: t.thumbnail?.title ?? null },
  };
}

/** Kiểm tra phía client trước khi lưu/render. durations: asset_id → giây. */
export function validateTimeline(t: Timeline, durations: Record<string, number>): string[] {
  const e: string[] = [];
  if (!t.clips.length) e.push("Timeline chưa có cảnh");
  t.clips.forEach((c, i) => {
    if (!c.asset_id) e.push(`Clip ${i + 1}: cảnh chưa có video`);
    const d = c.asset_id ? durations[c.asset_id] : undefined;
    if (c.trim_start < 0) e.push(`Clip ${i + 1}: điểm đầu phải ≥ 0`);
    if (c.trim_end !== null) {
      if (c.trim_end <= c.trim_start) e.push(`Clip ${i + 1}: điểm cuối phải lớn hơn điểm đầu`);
      if (d !== undefined && c.trim_end > d + 0.05) e.push(`Clip ${i + 1}: điểm cuối vượt thời lượng clip (${d.toFixed(1)}s)`);
    } else if (d !== undefined && c.trim_start >= d) e.push(`Clip ${i + 1}: điểm đầu vượt thời lượng clip`);
    if (c.volume < 0 || c.volume > 2) e.push(`Clip ${i + 1}: âm lượng 0–2`);
  });
  t.voiceover.forEach((v, i) => { if (!v.asset_id) e.push(`Voice-over ${i + 1}: chưa chọn file`); if (v.start < 0) e.push(`Voice-over ${i + 1}: thời điểm ≥ 0`); });
  if (t.music && !t.music.asset_id) e.push("Nhạc nền: chưa chọn file");
  if (t.logo && !t.logo.asset_id) e.push("Logo: chưa chọn file");
  return e;
}
