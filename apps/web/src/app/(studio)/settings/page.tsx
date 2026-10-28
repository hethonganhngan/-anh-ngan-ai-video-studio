"use client";
import { useSearchParams, useRouter } from "next/navigation";
import { PageHeader } from "@/components/app/page-header";
import { RequirePermission } from "@/components/app/require";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useAuth } from "@/hooks/use-auth";
import { RolesTab, UsersTab } from "@/features/settings/users";
import { ProvidersTab } from "@/features/settings/providers";
import { AuditTab, BackupTab, BudgetTab, HealthTab, ModeTab, PoliciesTab } from "@/features/settings/system";

const TABS: { key: string; label: string; perm: string }[] = [
  { key: "users", label: "Người dùng", perm: "admin.users" },
  { key: "roles", label: "Vai trò & phân quyền", perm: "admin.roles" },
  { key: "providers", label: "API Connections & AI Providers", perm: "admin.providers" },
  { key: "health", label: "Storage & System Health", perm: "admin.settings" },
  { key: "budget", label: "Ngân sách & chi phí", perm: "cost.view" },
  { key: "policies", label: "Chính sách & thông báo", perm: "admin.settings" },
  { key: "audit", label: "Audit Logs", perm: "admin.audit" },
  { key: "backup", label: "Backup", perm: "admin.backup" },
  { key: "mode", label: "Demo / Production", perm: "admin.settings" },
];

export default function SettingsPage() {
  const { has } = useAuth();
  const sp = useSearchParams();
  const router = useRouter();
  const tabs = TABS.filter((t) => has(t.perm));
  const cur = tabs.find((t) => t.key === sp.get("tab"))?.key ?? tabs[0]?.key ?? "users";
  return (
    <RequirePermission perm="admin.settings">
      <PageHeader code="M15" title="Cài đặt & quản trị hệ thống" description="Người dùng, phân quyền, kết nối API, ngân sách, audit, sao lưu và chế độ vận hành." />
      <Tabs value={cur} onValueChange={(v) => router.replace(`/settings?tab=${v}`)}>
        <TabsList>{tabs.map((t) => <TabsTrigger key={t.key} value={t.key} data-testid={`tab-${t.key}`}>{t.label}</TabsTrigger>)}</TabsList>
        <TabsContent value="users"><UsersTab /></TabsContent>
        <TabsContent value="roles"><RolesTab /></TabsContent>
        <TabsContent value="providers"><ProvidersTab /></TabsContent>
        <TabsContent value="health"><HealthTab /></TabsContent>
        <TabsContent value="budget"><BudgetTab /></TabsContent>
        <TabsContent value="policies"><PoliciesTab /></TabsContent>
        <TabsContent value="audit"><AuditTab /></TabsContent>
        <TabsContent value="backup"><BackupTab /></TabsContent>
        <TabsContent value="mode"><ModeTab /></TabsContent>
      </Tabs>
    </RequirePermission>
  );
}
