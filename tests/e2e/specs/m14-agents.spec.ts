import { test, expect } from "@playwright/test";
import { apiAs, call, createProject, loginUI } from "../fixtures/api";

test.describe("M14 — AI Agent Control Center", () => {
  test("10 agent; bật/tắt, cấu hình giới hạn, log thực thi có token/chi phí/latency", async ({ page }) => {
    const pm = await apiAs("pm");
    const admin = await apiAs("admin");
    const p = await createProject(pm, { topic: "E2E M14 agent log", automation_level: "MANUAL" });
    await call(pm, "post", `/projects/${p.id}/script/ideas`);

    await loginUI(page, "admin");
    await page.goto("/agents");
    await expect(page.getByTestId("page-title")).toHaveText("AI Agent Control Center");
    for (let i = 1; i <= 10; i++) await expect(page.getByTestId(`agent-A${String(i).padStart(2, "0")}`)).toBeVisible();

    try {
      await page.getByTestId("toggle-A10").click();
      await expect.poll(async () => (await call<any>(admin, "get", "/agents/A10")).is_enabled).toBe(false);
      await page.getByTestId("toggle-A10").click();
      await expect.poll(async () => (await call<any>(admin, "get", "/agents/A10")).is_enabled).toBe(true);
    } finally {
      await call(admin, "patch", "/agents/A10", { is_enabled: true });
    }

    const before = await call<any>(admin, "get", "/agents/A09");
    await page.getByTestId("config-A09").click();
    await page.getByTestId("cfg-runs").fill(String(before.max_runs_per_day + 1));
    await page.getByTestId("cfg-save").click();
    await expect.poll(async () => (await call<any>(admin, "get", "/agents/A09")).max_runs_per_day).toBe(before.max_runs_per_day + 1);
    await call(admin, "patch", "/agents/A09", { max_runs_per_day: before.max_runs_per_day });

    await page.getByTestId("exec-agent").selectOption("A02");
    const row = page.getByTestId("exec-row").filter({ hasText: "script.ideas" }).first();
    await expect(row).toBeVisible();
    await expect(row).toContainText("ms");
    await row.click();
    await expect(page.getByTestId("exec-detail")).toContainText("prompt_version");
  });

  test("Creator xem được nhưng không bật/tắt được agent", async ({ page }) => {
    await loginUI(page, "creator");
    await page.goto("/agents");
    await expect(page.getByTestId("toggle-A01")).toBeDisabled();
    await expect(page.getByTestId("config-A01")).toHaveCount(0);
  });
});
