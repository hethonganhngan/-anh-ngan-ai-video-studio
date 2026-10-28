"use client";
import type { ReactNode } from "react";
import { useAuth } from "@/hooks/use-auth";
import { AccessDenied, LoadingState } from "./states";

export function RequirePermission({ perm, children }: { perm: string; children: ReactNode }) {
  const { me, loading, has } = useAuth();
  if (loading || !me) return <LoadingState />;
  if (!has(perm)) return <AccessDenied perm={perm} />;
  return <>{children}</>;
}

export function Can({ perm, children, fallback = null }: { perm: string; children: ReactNode; fallback?: ReactNode }) {
  const { has } = useAuth();
  return <>{has(perm) ? children : fallback}</>;
}
