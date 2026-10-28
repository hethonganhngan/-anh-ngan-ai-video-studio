import { test, expect } from "@playwright/test";
import { execFileSync } from "child_process";
import { mkdtempSync, writeFileSync } from "fs";
import { tmpdir } from "os";
import { join } from "path";
import { apiAs, call, loginUI } from "../fixtures/api";

const dir = mkdtempSync(join(tmpdir(), "anngan-m12-"));
function png(name: string, color: string) {
  const p = join(dir, name);
  execFileSync("ffmpeg", ["-loglevel", "error", "-y", "-f", "lavfi", "-i", `color=c=${color}:s=320x320`, "-frames:v", "1", p]);
  return p;
}

test.describe("M12 — Thư viện tài nguyên", () => {
  test("upload hợp lệ, chặn file giả mạo, sửa tag, phiên bản mới, xoá", async ({ page }) => {
    const stamp = Date.now();
    const good = png(`logo_e2e_${stamp}.png`, "0x2563EB");
    const fake = join(dir, `fake_${stamp}.png`);
    writeFileSync(fake, "đây không phải ảnh png");
    const v2 = png(`logo_e2e_${stamp}_v2.png`, "0x10B981");

    await loginUI(page, "pm");
    await page.goto("/library");
    await expect(page.getByTestId("page-title")).toHaveText("Thư viện tài nguyên");
    await expect(page.getByTestId("storage-note")).toContainText("Object Storage");

    // File giả mạo bị từ chối
    await page.getByTestId("upload-file").setInputFiles(fake);
    await page.getByTestId("upload-type").selectOption("LOGO");
    await page.getByTestId("upload-submit").click();
    await expect(page.getByText("Nội dung file không khớp định dạng khai báo")).toBeVisible();

    // Upload hợp lệ
    await page.getByTestId("upload-file").setInputFiles(good);
    await page.getByTestId("upload-type").selectOption("LOGO");
    await page.getByTestId("upload-rights").selectOption("OWNED");
    await page.getByTestId("upload-tags").fill("logo, e2e");
    await page.getByTestId("upload-submit").click();
    const detail = page.getByTestId("asset-detail");
    await expect(detail).toContainText(`logo_e2e_${stamp}.png`);
    await expect(page.getByTestId("asset-meta")).toContainText("320×320");

    // Sửa tag & quyền
    await page.getByTestId("asset-tags").fill(`logo, e2e, tag${stamp}`);
    await page.getByTestId("asset-rights").selectOption("LICENSED");
    await page.getByTestId("asset-save").click();
    const pm = await apiAs("pm");
    await expect.poll(async () => (await call(pm, "get", `/assets?tag=tag${stamp}`)).items.length).toBe(1);
    const a1 = (await call(pm, "get", `/assets?tag=tag${stamp}`)).items[0];
    expect(a1.usage_rights).toBe("LICENSED");

    // Phiên bản mới
    await page.getByTestId("asset-version-file").setInputFiles(v2);
    await page.getByTestId("asset-version-submit").click();
    await expect.poll(async () => (await call(pm, "get", `/assets?tag=tag${stamp}`)).items[0]?.version_no).toBe(2);
    const a2 = (await call(pm, "get", `/assets?tag=tag${stamp}`)).items[0];
    expect(a2.parent_asset_id).toBe(a1.id);
    await page.getByTestId("lib-filter-tag").fill(`tag${stamp}`);
    await expect(page.getByTestId("lib-item")).toHaveCount(1);
    await page.getByTestId("lib-item").click();
    await expect(page.getByTestId("asset-versions").locator("li")).toHaveCount(2);

    // Xoá mềm
    await page.getByTestId("asset-delete").click();
    await page.getByTestId("confirm-ok").click();
    await expect(page.getByTestId("asset-detail")).toHaveCount(0);
    await expect(call(pm, "get", `/assets/${a2.id}`)).rejects.toThrow(/404/);
    // Xoá bản mới nhất → phiên bản trước (v1) hiển thị lại trong thư viện
    await expect.poll(async () => (await call(pm, "get", `/assets?tag=tag${stamp}`)).items.map((x: any) => x.version_no)).toEqual([1]);
    await expect(page.getByTestId("lib-item")).toHaveCount(1);
  });
});
