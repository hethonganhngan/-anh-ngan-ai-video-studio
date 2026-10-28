"use client";
import { assetUrl } from "@/lib/api";
import { cn } from "@/lib/utils";

export function VideoPlayer({ assetId, poster, className }: { assetId?: string | null; poster?: string | null; className?: string }) {
  if (!assetId) return <div className={cn("flex aspect-[9/16] items-center justify-center rounded-lg bg-slate-900 text-xs text-slate-400", className)}>Chưa có video</div>;
  return (
    <video key={assetId} controls preload="metadata" playsInline poster={poster ? assetUrl(poster) : undefined}
      className={cn("aspect-[9/16] w-full rounded-lg bg-black object-contain", className)} data-testid="video-player" crossOrigin="use-credentials">
      <source src={assetUrl(assetId)} type="video/mp4" />
    </video>
  );
}

export function AssetImage({ assetId, alt, className }: { assetId?: string | null; alt: string; className?: string }) {
  if (!assetId) return <div className={cn("flex items-center justify-center rounded-lg bg-slate-100 text-xs text-slate-400", className)}>—</div>;
  // eslint-disable-next-line @next/next/no-img-element
  return <img src={assetUrl(assetId)} alt={alt} className={cn("rounded-lg object-cover", className)} crossOrigin="use-credentials" />;
}
