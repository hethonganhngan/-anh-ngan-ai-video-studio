"use client";
import { createContext, useContext, useMemo, type ReactNode } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ApiError } from "@/lib/api";
import type { Me } from "@/types/api";

type AuthCtx = {
  me: Me | null; loading: boolean; error: unknown; has: (perm: string) => boolean; refresh: () => void; logout: () => Promise<void>;
};
const Ctx = createContext<AuthCtx | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const qc = useQueryClient();
  const q = useQuery<Me>({
    queryKey: ["me"], queryFn: () => api<Me>("/auth/me"), retry: false, staleTime: 60_000,
  });
  const value = useMemo<AuthCtx>(() => {
    const perms = new Set(q.data?.permissions ?? []);
    return {
      me: q.data ?? null, loading: q.isLoading, error: q.error, has: (p) => perms.has(p),
      refresh: () => qc.invalidateQueries({ queryKey: ["me"] }),
      logout: async () => {
        await api("/auth/logout", { method: "POST" }).catch(() => undefined);
        qc.clear();
        window.location.href = "/login";
      },
    };
  }, [q.data, q.isLoading, q.error, qc]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useAuth() {
  const v = useContext(Ctx);
  if (!v) throw new Error("useAuth must be inside AuthProvider");
  return v;
}

export const isUnauthorized = (e: unknown) => e instanceof ApiError && e.status === 401;
