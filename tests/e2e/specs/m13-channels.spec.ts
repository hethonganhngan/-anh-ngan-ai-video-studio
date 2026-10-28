import { test, expect } from "@playwright/test";
import { apiAs, call, loginUI } from "../fixtures/api";

test.describe("M13 — Kênh & Brand DNA", () => {
  test("4 kênh khởi tạo; tạo kênh mới, sửa Brand DNA tạo phiên bản & lịch sử, đổi nền tảng", async ({ page }) => {
    const code = `E2E${Date.now().toString().slice(-6)}`;
    await loginUI(page, "pm");
    await page.goto("/channels");
    await expect(page.getByTestId("page-title")).toHaveText("Quản lý kênh & Brand DNA");
    for (const n of ["Hệ thống Sữa Ánh Ngân", "Chuyện Nhà Mình", "Ba Phi Chuyện Đời", "Kiến thức Mẹ & Bé"]) {
      await expect(page.getByTestId("channel-list")).toContainText(n);
    }
    await page.getByTestId("channel-item").filter({ hasText: "Hệ thống Sữa Ánh Ngân" }).click();
    await expect(page.getByTestId("brand-slogan")).toHaveValue("TRAO NIỀM TIN – NHẬN GIÁ TRỊ");

    await page.getByTestId("new-channel").click();
    await page.getByTestId("ch-code").fill(code);
    await page.getByTestId("ch-name").fill(`Kênh thử ${code}`);
    await page.getByTestId("ch-create").click();
    await page.getByTestId("channel-item").filter({ hasText: code }).click();
    await expect(page.getByTestId("channel-name")).toHaveText(`Kênh thử ${code}`);

    await page.getByTestId("brand-slogan").fill("Slogan thử nghiệm");
    await page.getByTestId("brand-forbidden_terms").fill("tốt nhất\nthần kỳ");
    await page.getByTestId("brand-note").fill("E2E cập nhật DNA");
    await page.getByTestId("brand-save").click();
    await expect(page.getByText("DNA v2")).toBeVisible();
    await page.getByTestId("platform-TIKTOK").click();

    const pm = await apiAs("pm");
    const chs = await call<any[]>(pm, "get", "/channels");
    const ch = chs.find((c) => c.code === code);
    expect(ch.brand.slogan).toBe("Slogan thử nghiệm");
    expect(ch.brand.forbidden_terms).toEqual(["tốt nhất", "thần kỳ"]);
    expect(ch.brand.version_no).toBe(2);
    expect(ch.brand.history).toHaveLength(1);
    await expect.poll(async () => (await call<any[]>(pm, "get", "/channels")).find((c) => c.code === code).platforms).toContain("TIKTOK");

    await page.getByTestId("brand-history-toggle").click();
    await expect(page.getByTestId("brand-history")).toContainText("E2E cập nhật DNA");
  });

  test("Creator chỉ xem, không sửa được Brand DNA", async ({ page }) => {
    await loginUI(page, "creator");
    await page.goto("/channels");
    await expect(page.getByTestId("brand-editor")).toBeVisible();
    await expect(page.getByTestId("brand-save")).toHaveCount(0);
    await expect(page.getByTestId("new-channel")).toHaveCount(0);
  });
});
