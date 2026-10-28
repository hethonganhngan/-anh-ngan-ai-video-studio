import { api } from "@/lib/api";
import type { Asset } from "@/types/api";

/** Tải 1 file lên Thư viện và trả về asset. */
export async function uploadAsset(file: File, assetType: string, opts: { rights?: string; tags?: string; channelId?: string | null; name?: string } = {}) {
  const fd = new FormData();
  fd.append("file", file);
  fd.append("asset_type", assetType);
  fd.append("usage_rights", opts.rights ?? "OWNED");
  fd.append("tags", opts.tags ?? "");
  if (opts.channelId) fd.append("channel_id", opts.channelId);
  if (opts.name) fd.append("name", opts.name);
  return api<Asset>("/assets", { form: fd });
}
