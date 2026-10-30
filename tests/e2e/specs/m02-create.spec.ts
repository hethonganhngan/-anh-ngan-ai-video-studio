import { test, expect } from "@playwright/test";
import { apiAs, call, loginUI } from "../fixtures/api";

test.describe("M02 — Trung tâm tạo video", () => {
  test("kiểm tra dữ liệu, ước tính chi phí, tạo 1 video không trùng khi bấm 2 lần", async ({ page }) => {
    const topic = `E2E M02 chọn sữa cho bé ${Date.now()}`;
    await loginUI(page, "creator");
    await page.goto("/create");
    await expect(page.getByTestId("page-title")).toHaveText("Trung tâm tạo video");
    // Validation
    await page.getByTestId("f-duration").fill("4");
    await page.getByTestId("create-submit").click();
    await expect(page.getByText("Chủ đề tối thiểu 5 ký tự")).toBeVisible();
    await expect(page.getByText("Tối thiểu 8 giây")).toBeVisible();
    // Ước tính
    await page.getByTestId("f-duration").fill("24");
    await expect(page.getByTestId("est-scenes")).toContainText("3 × 8s");
    await expect(page.getByTestId("est-video")).toContainText("36.000");
    await page.getByTestId("f-topic").fill(topic);
    await page.getByTestId("f-cta").fill("Ghé Ánh Ngân để được tư vấn");
    await page.getByTestId("f-automation").selectOption("MANUAL");
    await page.getByTestId("f-run-director").uncheck();  // mặc định bật (AUTO chạy một mạch) — test này chỉ kiểm tra tạo
    // Bấm 2 lần liên tiếp — idempotency key chống tạo trùng
    // Gửi form 2 lần liên tiếp đồng bộ (mô phỏng double-click) — cùng idempotency key
    await page.getByTestId("create-form").evaluate((f: HTMLFormElement) => { f.requestSubmit(); f.requestSubmit(); });
    await page.waitForURL(/\/projects\/[0-9a-f-]{36}$/);
    const pm = await apiAs("pm");
    const list = await call<any>(pm, "get", `/projects?q=${encodeURIComponent(topic)}`);
    expect(list.total).toBe(1);
    const p = list.items[0];
    expect(p.duration_sec).toBe(24);
    expect(p.cta).toBe("Ghé Ánh Ngân để được tư vấn");
    expect(p.automation_level).toBe("MANUAL");
    expect(p.status).toBe("CREATED");
  });

  test("tạo lô 2 video và chạy AI Director", async ({ page }) => {
    const topic = `E2E M02 lô video ${Date.now()}`;
    await loginUI(page, "pm");
    await page.goto("/create");
    await page.getByTestId("f-topic").fill(topic);
    await page.getByTestId("f-duration").fill("8");
    await page.getByTestId("f-quantity").fill("2");
    await page.getByTestId("f-automation").selectOption("MANUAL");
    await page.getByTestId("f-run-director").check();
    await expect(page.getByTestId("create-submit")).toContainText("Tạo lô 2 video");
    await page.getByTestId("create-submit").click();
    await page.waitForURL(/\/projects$/);
    const pm = await apiAs("pm");
    const list = await call<any>(pm, "get", `/projects?q=${encodeURIComponent(topic)}`);
    expect(list.total).toBe(2);
    expect(list.items[0].batch_id).toBeTruthy();
    expect(list.items[0].batch_id).toBe(list.items[1].batch_id);
    // AI Director (MANUAL) đã chạy 1 bước: tạo 3 ý tưởng
    for (const p of list.items) expect(p.status).toBe("SCRIPT_GENERATING");
  });
});
