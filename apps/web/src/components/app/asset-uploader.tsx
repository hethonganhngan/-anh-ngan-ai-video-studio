"use client";
import { useRef, useState } from "react";
import { Upload } from "lucide-react";
import { toast } from "sonner";
import { api, errorMessage } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input, NativeSelect } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ASSET_TYPES, USAGE_RIGHTS } from "@/lib/labels";
import type { Asset } from "@/types/api";

export function AssetUploader({ defaultType = "IMAGE", lockType, channelId, projectId, accept, onUploaded, compact }: {
  defaultType?: string; lockType?: boolean; channelId?: string | null; projectId?: string | null; accept?: string;
  onUploaded?: (a: Asset) => void; compact?: boolean;
}) {
  const fileRef = useRef<HTMLInputElement>(null);
  const [type, setType] = useState(defaultType);
  const [rights, setRights] = useState("OWNED");
  const [tags, setTags] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    const f = fileRef.current?.files?.[0];
    if (!f) { toast.error("Chọn file trước"); return; }
    const fd = new FormData();
    fd.append("file", f);
    fd.append("asset_type", type);
    fd.append("usage_rights", rights);
    fd.append("tags", tags);
    if (channelId) fd.append("channel_id", channelId);
    if (projectId) fd.append("project_id", projectId);
    setBusy(true);
    try {
      const a = await api<Asset>("/assets", { form: fd });
      toast.success(`Đã tải lên ${a.name}`);
      if (fileRef.current) fileRef.current.value = "";
      onUploaded?.(a);
    } catch (e) {
      toast.error(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className={compact ? "flex flex-wrap items-end gap-2" : "grid gap-3 md:grid-cols-5 md:items-end"} data-testid="asset-uploader">
      <div className="md:col-span-2">
        <Label>File</Label>
        <Input ref={fileRef} type="file" accept={accept} data-testid="upload-file" />
      </div>
      {!lockType && (
        <div>
          <Label>Loại</Label>
          <NativeSelect value={type} onChange={(e) => setType(e.target.value)} data-testid="upload-type">
            {Object.entries(ASSET_TYPES).filter(([k]) => !["EXPORT", "THUMBNAIL"].includes(k)).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </NativeSelect>
        </div>
      )}
      <div>
        <Label>Quyền sử dụng</Label>
        <NativeSelect value={rights} onChange={(e) => setRights(e.target.value)} data-testid="upload-rights">
          {Object.entries(USAGE_RIGHTS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </NativeSelect>
      </div>
      {!compact && (
        <div>
          <Label>Tag (phân cách dấu phẩy)</Label>
          <Input value={tags} onChange={(e) => setTags(e.target.value)} placeholder="logo, ánh ngân" data-testid="upload-tags" />
        </div>
      )}
      <Button onClick={submit} loading={busy} data-testid="upload-submit"><Upload />Tải lên</Button>
    </div>
  );
}
