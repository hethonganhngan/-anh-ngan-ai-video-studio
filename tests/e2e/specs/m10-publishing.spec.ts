import { test, expect } from "@playwright/test";
import { apiAs, call, createProject, loginUI, toApproved } from "../fixtures/api";

test.describe("M10 — Publishing & Analytics", () => {
  test("lên lịch, caption vi phạm bị chặn, xuất file, đánh dấu đăng, nhập analytics", async ({ page }) => {
    const pm = await apiAs("pm");
    const p = await createProject(pm, { topic: "E2E M10 phát hành video tã mùa nóng" });
    await toApproved(p.id);

    await loginUI(page, "publisher");
    await page.goto("/publishing");
    await expect(page.getByTestId("page-title")).toHaveText("Publishing & Analytics");
    await expect(page.getByTestId("pub-api-note")).toContainText("API chính thức");
    await page.getByTestId("tab-approved").click();
    await page.getByTestId("approved-row").filter({ hasText: p.code }).getByTestId("pub-schedule").click();
    await page.getByTestId("pub-platform").selectOption("FACEBOOK");
    await page.getByTestId("pub-caption").fill("Sữa tốt nhất cho bé, cam kết tăng cân");
    await expect(page.getByTestId("caption-check")).toContainText("MAJOR");
    await expect(page.getByTestId("pub-create-submit")).toBeDisabled();
    await page.getByTestId("pub-caption").fill("Ánh Ngân đồng hành cùng mẹ chọn tã phù hợp mùa nóng");
    await expect(page.getByTestId("caption-check")).toContainText("qua bộ lọc");
    const d = new Date(Date.now() + 2 * 86400000);
    const local = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}T09:30`;
    await page.getByTestId("pub-when").fill(local);
    await page.getByTestId("pub-create-submit").click();

    let pub: any;
    await expect.poll(async () => {
      pub = (await call<any[]>(pm, "get", "/publications/calendar")).find((x) => x.project_id === p.id);
      return pub?.status;
    }).toBe("SCHEDULED");
    await page.getByRole("tab", { name: "Lịch nội dung" }).click();
    await expect(page.getByTestId("cal-item").filter({ hasText: p.code })).toBeVisible();

    await page.getByTestId("tab-posts").click();
    const row = page.locator(`[data-pub-id="${pub.id}"]`);
    await row.getByTestId("pub-api").click();
    await expect(page.getByText("Dữ liệu DEMO không được tự động xuất bản")).toBeVisible();
    await row.getByTestId("pub-export").click();
    await expect(row.getByTestId("pub-download")).toBeVisible();
    await expect(row).toContainText("Đã xuất file");
    const zip = await page.request.get(await row.getByTestId("pub-download").getAttribute("href") as string);
    expect((await zip.body()).subarray(0, 2).toString()).toBe("PK");
    expect((await call(pm, "get", `/projects/${p.id}`)).status).toBe("PUBLISH_QUEUED");

    await row.getByTestId("pub-mark").click();
    await page.getByTestId("pub-url").fill("https://www.tiktok.com/@anhngan/video/1");
    await page.getByTestId("pub-url-submit").click();
    await expect(page.getByText("URL không thuộc FACEBOOK", { exact: false })).toBeVisible();
    await page.getByTestId("pub-url").fill("https://www.facebook.com/anhngan/videos/987654");
    await page.getByTestId("pub-url-submit").click();
    await expect(row).toContainText("Đã đăng");
    await expect.poll(async () => (await call(pm, "get", `/projects/${p.id}`)).status).toBe("PUBLISHED");

    await row.getByTestId("pub-snapshot").click();
    await page.getByTestId("snap-views").fill("2000");
    await page.getByTestId("snap-likes").fill("150");
    await page.getByTestId("snap-comments").fill("30");
    await page.getByTestId("snap-shares").fill("20");
    await page.getByTestId("snap-retention_rate").fill("45");
    await page.getByTestId("snap-submit").click();
    await page.getByTestId("tab-analytics").click();
    const perfRow = page.getByTestId("perf-row").filter({ hasText: p.code });
    await expect(perfRow.getByTestId("perf-engagement")).toHaveText("10%");
    await expect(page.getByTestId("perf-chart")).toBeVisible();
    await page.getByTestId("run-insights").click();
    await expect(page.getByTestId("insights")).toContainText(/Trung vị|Cần ít nhất 2 video/);
    await expect.poll(async () => (await call(pm, "get", `/projects/${p.id}`)).status).toBe("ANALYTICS_COLLECTION");
  });
});
