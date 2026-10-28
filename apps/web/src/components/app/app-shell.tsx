"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { Bell, LogOut, Menu, Sparkles, X } from "lucide-react";
import { useAuth, isUnauthorized } from "@/hooks/use-auth";
import { NAV } from "@/lib/nav";
import { api } from "@/lib/api";
import { cn, formatDate } from "@/lib/utils";
import { ModeBadge } from "./status-badge";
import { LoadingState } from "./states";
import { Button } from "@/components/ui/button";

type Noti = { id: string; level: string; title: string; message: string; link: string | null; read_at: string | null; created_at: string };

export function AppShell({ children }: { children: ReactNode }) {
  const { me, loading, error, has, logout } = useAuth();
  const router = useRouter();
  const path = usePathname();
  const [open, setOpen] = useState(false);
  const [showNoti, setShowNoti] = useState(false);
  const noti = useQuery<Noti[]>({ queryKey: ["notifications"], queryFn: () => api("/admin/notifications"), enabled: !!me && has("dashboard.view"), refetchInterval: 30_000 });

  useEffect(() => {
    if (!loading && (isUnauthorized(error) || (!me && error))) router.replace(`/login?next=${encodeURIComponent(path)}`);
  }, [loading, error, me, router, path]);
  useEffect(() => setOpen(false), [path]);

  if (loading || !me) return <div className="p-10"><LoadingState rows={4} /></div>;
  const unread = (noti.data ?? []).filter((n) => !n.read_at).length;

  return (
    <div className="flex min-h-screen">
      <aside className={cn("fixed inset-y-0 left-0 z-40 w-64 transform bg-navy-900 text-slate-200 transition-transform lg:static lg:translate-x-0", open ? "translate-x-0" : "-translate-x-full")} data-testid="sidebar">
        <div className="flex h-16 items-center gap-2 border-b border-navy-700 px-5">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-600"><Sparkles className="h-5 w-5 text-white" /></div>
          <div className="leading-tight">
            <p className="text-sm font-bold text-white">Ánh Ngân</p>
            <p className="text-[11px] text-slate-400">AI Video Studio V2.0</p>
          </div>
          <button className="ml-auto lg:hidden" onClick={() => setOpen(false)} aria-label="Đóng menu"><X className="h-5 w-5" /></button>
        </div>
        <nav className="h-[calc(100vh-4rem)] overflow-y-auto px-3 py-4 scrollbar-thin" aria-label="Điều hướng chính">
          {NAV.map((g, gi) => (
            <div key={g.label} className="mb-4">
              <p className="mb-1 px-3 text-[11px] font-semibold uppercase tracking-wider text-slate-500">Nhóm {gi + 1} — {g.label}</p>
              {g.items.map((it) => {
                const active = path === it.href || path.startsWith(it.href + "/");
                const allowed = has(it.perm);
                return (
                  <Link key={it.href} href={it.href} data-testid={`nav-${it.code}`} aria-current={active ? "page" : undefined}
                    className={cn("mb-0.5 flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition",
                      active ? "bg-brand-600 text-white" : "text-slate-300 hover:bg-navy-800 hover:text-white",
                      !allowed && "opacity-40")}>
                    <it.icon className="h-4 w-4 shrink-0" />
                    <span className="truncate">{it.label}</span>
                    <span className="ml-auto text-[10px] text-slate-400">{it.code}</span>
                  </Link>
                );
              })}
            </div>
          ))}
        </nav>
      </aside>
      {open && <div className="fixed inset-0 z-30 bg-black/40 lg:hidden" onClick={() => setOpen(false)} />}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-20 flex h-16 items-center gap-3 border-b border-slate-200 bg-white/90 px-4 backdrop-blur md:px-6">
          <button className="lg:hidden" onClick={() => setOpen(true)} aria-label="Mở menu"><Menu className="h-5 w-5" /></button>
          <ModeBadge mode={me.mode} />
          {me.is_demo && <span className="hidden text-xs text-slate-500 md:inline">Tài khoản DEMO</span>}
          <div className="relative ml-auto">
            <Button variant="ghost" size="icon" onClick={() => setShowNoti((v) => !v)} aria-label="Thông báo" data-testid="noti-button">
              <Bell />
              {unread > 0 && <span className="absolute right-1 top-1 rounded-full bg-red-500 px-1 text-[10px] text-white">{unread}</span>}
            </Button>
            {showNoti && (
              <div className="absolute right-0 top-11 z-50 w-80 rounded-xl border border-slate-200 bg-white p-2 shadow-lg">
                <div className="flex items-center justify-between px-2 py-1">
                  <p className="text-sm font-semibold">Thông báo</p>
                  <button className="text-xs text-brand-600" onClick={async () => { await api("/admin/notifications/read-all", { method: "POST" }); noti.refetch(); }}>Đánh dấu đã đọc</button>
                </div>
                <div className="max-h-80 overflow-y-auto">
                  {(noti.data ?? []).length === 0 && <p className="p-3 text-sm text-slate-500">Không có thông báo</p>}
                  {(noti.data ?? []).slice(0, 20).map((n) => (
                    <Link key={n.id} href={n.link ?? "#"} className={cn("block rounded-lg p-2 text-sm hover:bg-slate-50", !n.read_at && "bg-brand-50/50")} onClick={() => setShowNoti(false)}>
                      <p className={cn("font-medium", n.level === "CRITICAL" ? "text-red-700" : n.level === "WARNING" ? "text-amber-700" : "text-slate-800")}>{n.title}</p>
                      <p className="text-xs text-slate-500">{n.message}</p>
                      <p className="text-[10px] text-slate-400">{formatDate(n.created_at)}</p>
                    </Link>
                  ))}
                </div>
              </div>
            )}
          </div>
          <div className="text-right leading-tight">
            <p className="text-sm font-medium text-slate-800" data-testid="current-user">{me.full_name}</p>
            <p className="text-xs text-slate-500">{me.role.name}</p>
          </div>
          <Button variant="ghost" size="icon" onClick={logout} aria-label="Đăng xuất" data-testid="logout"><LogOut /></Button>
        </header>
        {me.must_change_password && (
          <div className="border-b border-amber-200 bg-amber-50 px-6 py-2 text-sm text-amber-900">
            Bạn đang dùng mật khẩu khởi tạo. <Link className="font-medium underline" href="/account">Đổi mật khẩu ngay</Link>.
          </div>
        )}
        <main className="flex-1 p-4 md:p-6">{children}</main>
      </div>
    </div>
  );
}
