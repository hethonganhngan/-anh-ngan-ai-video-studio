import { test, expect } from "@playwright/test";
import { loginUI, USERS } from "../fixtures/api";

test.describe("Đăng nhập & khung ứng dụng", () => {
  test("sai mật khẩu hiển thị lỗi; đúng thì vào Dashboard", async ({ page }) => {
    await page.goto("/dashboard");
    await expect(page).toHaveURL(/\/login\?next=/);
    await page.getByTestId("login-email").fill(USERS.admin[0]);
    await page.getByTestId("login-password").fill("sai-mat-khau");
    await page.getByTestId("login-submit").click();
    await expect(page.getByTestId("login-error")).toContainText("không đúng");
    await page.getByTestId("login-password").fill(USERS.admin[1]);
    await page.getByTestId("login-submit").click();
    await expect(page).toHaveURL(/\/dashboard/);
    await expect(page.getByTestId("current-user")).toHaveText("CEO / Super Admin");
    await expect(page.getByTestId("mode-badge")).toContainText("DEMO");
  });

  test("sidebar có đủ 15 màn hình chia 5 nhóm", async ({ page }) => {
    await loginUI(page, "admin");
    const sidebar = page.getByTestId("sidebar");
    for (let i = 1; i <= 15; i++) {
      await expect(sidebar.getByTestId(`nav-M${String(i).padStart(2, "0")}`)).toBeVisible();
    }
    for (const g of ["Điều hành", "Sản xuất", "Chất lượng", "Nội dung", "Hệ thống"]) {
      await expect(sidebar).toContainText(g);
    }
  });

  test("Viewer không truy cập được Cài đặt & quản trị", async ({ page }) => {
    await loginUI(page, "viewer");
    await page.goto("/settings");
    await expect(page.getByTestId("state-denied")).toBeVisible();
  });

  test("đăng xuất", async ({ page }) => {
    await loginUI(page, "pm");
    await page.getByTestId("logout").click();
    await expect(page).toHaveURL(/\/login/);
  });
});
