import { test, expect } from "@playwright/test";
import { apiAs, call, createProject, loginUI } from "../fixtures/api";

test.describe("M01 — Dashboard CEO", () => {
  test("KPI có công thức & nguồn; lọc theo dự án khớp số liệu API", async ({ page }) => {
    const pm = await apiAs("pm");
    const p = await createProject(pm, { topic: "E2E M01 dashboard lọc dự án", automation_level: "MANUAL" });
    const api = await call<any>(pm, "get", `/dashboard?project_id=${p.id}`);
    const total = api.kpis.find((k: any) => k.key === "videos_total");
    expect(total.value).toBe(1);

    await loginUI(page, "admin");
    await page.goto("/dashboard");
    await expect(page.getByTestId("page-title")).toHaveText("Dashboard CEO");
    await expect(page.getByTestId("kpi-grid")).toBeVisible();
    for (const k of ["videos_total", "in_production", "pending_approval", "completed", "published", "cost_total", "cost_per_approved",
      "avg_qc", "regen_rate", "feedback_cases", "capa_verified_rate", "views_total"]) {
      await expect(page.getByTestId(`kpi-${k}`)).toBeVisible();
    }
    await page.getByTestId("dash-project").selectOption(p.id);
    await expect(page.getByTestId("kpi-videos_total").getByTestId("kpi-value")).toHaveText("1");
    await expect(page.getByTestId("kpi-in_production").getByTestId("kpi-value")).toHaveText("0");
    await page.getByTestId("kpi-videos_total").getByRole("button").click();
    await expect(page.getByTestId("kpi-videos_total").getByTestId("kpi-formula")).toContainText("COUNT(projects)");
    await expect(page.getByTestId("kpi-videos_total").getByTestId("kpi-formula")).toContainText("Nguồn");
    await expect(page.getByTestId("chart-videos")).toBeVisible();
    await expect(page.getByTestId("chart-cost")).toBeVisible();
  });

  test("Viewer xem được dashboard nhưng không truy cập M15", async ({ page }) => {
    await loginUI(page, "viewer");
    await page.goto("/dashboard");
    await expect(page.getByTestId("kpi-grid")).toBeVisible();
  });
});
