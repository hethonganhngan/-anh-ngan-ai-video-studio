"use client";
import { Suspense } from "react";
import { AuthProvider } from "@/hooks/use-auth";
import { AppShell } from "@/components/app/app-shell";
import { LoadingState } from "@/components/app/states";

export default function StudioLayout({ children }: { children: React.ReactNode }) {
  return (
    <AuthProvider>
      <AppShell>
        <Suspense fallback={<LoadingState />}>{children}</Suspense>
      </AppShell>
    </AuthProvider>
  );
}
