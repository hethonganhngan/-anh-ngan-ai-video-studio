import { test, expect } from "@playwright/test";
import { apiAs, call, createProject, loginUI } from "../fixtures/api";

test.describe("M11 — Quản lý dự án & hàng đợi", () => {
  test("lọc dự án, xem Kanban, chi tiết, AI Director chạy tiếp và huỷ dự án", async ({ page }) => {
    const pm = await apiAs("pm");
    const p = await createProject(pm, { topic: "E2E M11 kiểm tra tiến độ dự án", automation_level: "MANUAL" });
    await loginUI(page, "pm");
    await page.goto("/projects");
    await expect(page.getByTestId("page-title")).toHaveText("Quản lý dự án & hàng đợi");
    await page.getByTestId("filter-q").fill(p.code);
    await expect(page.getByTestId("project-row")).toHaveCount(1);
    await expect(page.getByTestId("project-row")).toContainText("Khởi tạo");

    await page.getByTestId("tab-kanban").click();
    await expect(page.getByTestId("kanban-card").filter({ hasText: p.code })).toBeVisible();

    await page.goto(`/projects/${p.id}`);
    await page.getByTestId("advance").click();  // MANUAL: A02 tạo 3 ý tưởng, dừng chờ chọn
    await expect(page.getByTestId("event-log")).toContainText("A02 tạo 3 ý tưởng");
    const after = await call(pm, "get", `/projects/${p.id}`);
    expect(after.status).toBe("SCRIPT_GENERATING");

    await page.getByTestId("cancel-project").click();
    await page.getByTestId("confirm-reason").fill("E2E huỷ thử");
    await page.getByTestId("confirm-ok").click();
    await expect(page.getByTestId("event-log")).toContainText("E2E huỷ thử");
    expect((await call(pm, "get", `/projects/${p.id}`)).status).toBe("CANCELLED");
  });

  test("hàng đợi: tác vụ lỗi hiển thị và retry được", async ({ page }) => {
    const pm = await apiAs("pm");
    const p = await createProject(pm, { topic: "E2E M11 hàng đợi lỗi", automation_level: "MANUAL", duration_sec: 8 });
    await call(pm, "post", `/projects/${p.id}/script/ideas`);
    await call(pm, "post", `/projects/${p.id}/script/select-idea`, { index: 0 });
    await call(pm, "post", `/projects/${p.id}/script/write`);
    const view = await call(pm, "get", `/projects/${p.id}/script`);
    const s = view.scenes[0];
    // Tiêm lỗi vĩnh viễn vào cảnh → hết lượt retry tự động
    await call(pm, "patch", `/scenes/${s.id}`, { action: s.action + " [[MOCK_FAIL]]", note: "tiêm lỗi" });
    await call(pm, "post", `/projects/${p.id}/script/approve`, { comment: "ok" });
    await call(pm, "post", `/projects/${p.id}/validate-assets`);
    await call(pm, "post", `/projects/${p.id}/generate`, {});
    await loginUI(page, "pm");
    await page.goto("/projects");
    await page.getByTestId("tab-queue").click();
    await page.getByTestId("queue-status").selectOption("FAILED");
    await expect(page.getByTestId("job-row").first()).toContainText("Lỗi");
    await page.goto(`/projects/${p.id}`);
    await expect(page.getByTestId("last-error")).toContainText("Cảnh 1");
  });
});
