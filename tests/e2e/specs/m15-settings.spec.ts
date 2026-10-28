import { test, expect } from "@playwright/test";
import { apiAs, call, loginUI } from "../fixtures/api";

test.describe("M15 — Cài đặt & quản trị", () => {
  test("tạo người dùng, đổi vai trò, audit log ghi nhận", async ({ page }) => {
    const email = `e2e${Date.now()}@anhngan.local`;
    await loginUI(page, "admin");
    await page.goto("/settings?tab=users");
    await expect(page.getByTestId("page-title")).toHaveText("Cài đặt & quản trị hệ thống");
    await page.getByTestId("new-user").click();
    await page.getByTestId("u-email").fill(email);
    await page.getByTestId("u-name").fill("Người dùng E2E");
    await page.getByTestId("u-role").selectOption("VIEWER");
    await page.getByTestId("u-password").fill("Abcdefgh12345");
    await page.getByTestId("u-create").click();
    const row = page.getByTestId("user-row").filter({ hasText: email });
    await expect(row).toBeVisible();
    await row.getByTestId("user-role").selectOption("PUBLISHER");
    const admin = await apiAs("admin");
    await expect.poll(async () => (await call<any[]>(admin, "get", "/admin/users")).find((u) => u.email === email)?.role.code).toBe("PUBLISHER");

    await page.getByTestId("tab-audit").click();
    await page.getByTestId("audit-action").fill("user.");
    await expect(page.getByTestId("audit-row").filter({ hasText: "user.update" }).first()).toBeVisible();
  });

  test("API key chỉ hiện 4 ký tự cuối; ngân sách; backup; health; ma trận quyền", async ({ page }) => {
    const admin = await apiAs("admin");
    await loginUI(page, "admin");
    await page.goto("/settings?tab=providers");
    const prov = page.getByTestId("prov-tts_none");
    await prov.getByTestId("prov-edit").click();
    await page.getByTestId("prov-key").fill("sk-test-SECRET-9876");
    await page.getByTestId("prov-save").click();
    await expect(prov.getByTestId("prov-secret")).toHaveText("****9876");
    await expect(prov.getByTestId("prov-status")).toContainText("chưa xác minh");
    const provs = await call<any[]>(admin, "get", "/admin/providers");
    const t = provs.find((p) => p.provider_code === "tts_none");
    expect(JSON.stringify(t)).not.toContain("SECRET");
    expect(t.connection_status).toBe("CONFIGURED_UNVERIFIED");

    await page.getByTestId("tab-budget").click();
    await page.getByTestId("b-scope").selectOption("PROVIDER");
    await page.getByTestId("b-ref").fill("manual_flow");
    await page.getByTestId("b-period").selectOption("DAILY");
    await page.getByTestId("b-limit").fill("777000");
    await page.getByTestId("b-save").click();
    await expect(page.getByTestId("budget-row").filter({ hasText: "777.000" })).toBeVisible();
    const budgets = await call<any[]>(admin, "get", "/admin/budgets");
    const b = budgets.find((x) => x.scope === "PROVIDER" && x.scope_ref === "manual_flow" && x.period === "DAILY");
    expect(Number(b.limit_amount)).toBe(777000);
    await call(admin, "delete", `/admin/budgets/${b.id}`);

    await page.getByTestId("tab-backup").click();
    const before = (await call<any>(admin, "get", "/admin/backups")).files.length;
    await page.getByTestId("backup-create").click();
    await expect.poll(async () => (await call<any>(admin, "get", "/admin/backups")).files.length).toBe(before + 1);
    await expect(page.getByTestId("backup-row").first()).toContainText(".dump");

    await page.getByTestId("tab-health").click();
    await expect(page.getByTestId("check-database")).toContainText("PostgreSQL");
    await page.getByTestId("tab-roles").click();
    await expect(page.getByTestId("roles-matrix")).toContainText("project.approve");
  });

  test("phân quyền: Publisher và Viewer bị chặn", async ({ page }) => {
    await loginUI(page, "publisher");
    await page.goto("/settings");
    await expect(page.getByTestId("state-denied")).toBeVisible();
  });

  test("chuyển Demo → Production cần gõ xác nhận, rồi quay lại DEMO", async ({ page }) => {
    const admin = await apiAs("admin");
    try {
      await loginUI(page, "admin");
      await page.goto("/settings?tab=mode");
      await page.getByTestId("mode-switch").click();
      await expect(page.getByTestId("confirm-ok")).toBeDisabled();
      await page.getByTestId("confirm-input").fill("PRODUCTION");
      await page.getByTestId("confirm-ok").click();
      await expect(page.getByTestId("mode-badge").first()).toHaveText("PRODUCTION");
      expect((await call<any>(admin, "get", "/auth/me")).mode).toBe("PRODUCTION");
    } finally {
      await call(admin, "post", "/admin/mode", { mode: "DEMO", confirm_text: "DEMO" });
    }
    expect((await call<any>(admin, "get", "/auth/me")).mode).toBe("DEMO");
  });
});
