export type ChannelFull = { id: string; code: string; name: string; platforms: string[] };
export type PerfRow = {
  publication_id: string; project_id: string; project_code: string; title: string; channel_id: string; platform: string;
  post_url: string | null; published_at: string | null; views: number; likes: number; comments: number; shares: number; saves: number;
  retention_rate: number | null; avg_watch_sec: number | null; conversions: number | null; engagement_rate: number | null;
  cost: number; cost_per_1k_views: number | null; cost_per_conversion: number | null; has_data: boolean; data_mode: string;
};
export type Insights = { insights: string[]; anomalies: { publication_id: string; project_code: string; reason: string }[] };
export const PLATFORM_LABEL: Record<string, string> = { FACEBOOK: "Facebook", TIKTOK: "TikTok", YOUTUBE: "YouTube", ZALO: "Zalo OA" };
