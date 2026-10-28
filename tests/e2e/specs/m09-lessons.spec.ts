import { test, expect } from "@playwright/test";
import { apiAs, call, loginUI } from "../fixtures/api";

async function active(code: string) {
  const pm = await apiAs("pm");
  const t = (await call<any[]>(pm, "get", "/prompts/templates")).find((x) => x.code === code);
  return { id: t.active_version_id as string, no: t.active_version_no as number };
}

test.describe("M09 — AI Lessons Learned", () => {
  test("tạo → gửi duyệt → duyệt → áp dụng (prompt tăng phiên bản) → rollback", async ({ page }) => {
    const before = await active("A03.scene_prompt");
    const title = `E2E bài học ánh sáng ngược ${Date.now()}`;
    await loginUI(page, "pm");
    await page.goto("/lessons");
    await expect(page.getByTestId("page-title")).toHaveText("AI Lessons Learned");
    await page.getByTestId("ll-new").click();
    await page.getByTestId("ll-type").selectOption("EFFECTIVE_PROMPT");
    await page.getByTestId("ll-title").fill(title);
    await page.getByTestId("ll-lesson").fill("Tránh cảnh ngược sáng làm tối khuôn mặt nhân vật");
    await page.getByTestId("ll-template").selectOption("A03.scene_prompt");
    await page.getByTestId("ll-neg").fill("ngược sáng làm tối khuôn mặt");
    await page.getByTestId("ll-rule").fill("Luôn có ánh sáng phụ chiếu sáng khuôn mặt");
    await page.getByTestId("ll-create-submit").click();
    const detail = page.getByTestId("lesson-detail");
    await expect(detail).toContainText(title);
    await expect(detail).toContainText("Chỉ áp dụng vào cấu hình chuẩn sau khi bài học được duyệt");
    await expect(page.getByTestId("lesson-apply")).toHaveCount(0);

    await page.getByTestId("lesson-submit").click();
    await expect(detail).toContainText("Chờ duyệt");
    await page.getByTestId("lesson-approve").click();
    await expect(detail).toContainText("Đã duyệt");
    await page.getByTestId("lesson-apply").click();
    await expect(detail).toContainText("Đã áp dụng");
    await expect(page.getByTestId("pv-Sau")).toContainText("ngược sáng làm tối khuôn mặt");
    await expect(page.getByTestId("pv-Trước")).toBeVisible();
    const pm = await apiAs("pm");
    const lesson = (await call(pm, "get", `/lessons?q=${encodeURIComponent(title)}`)).items[0];
    expect(lesson.previous_prompt_version_id).toBe(before.id);
    const after = await active("A03.scene_prompt");
    expect(after.id).toBe(lesson.applied_prompt_version_id);
    expect(after.no).toBeGreaterThan(before.no);

    await page.getByTestId("lesson-rollback").click();
    await page.getByTestId("confirm-reason").fill("Gây quá sáng ở cảnh đêm");
    await page.getByTestId("confirm-ok").click();
    await expect(detail).toContainText("Đã rollback");
    await expect.poll(async () => (await active("A03.scene_prompt")).id).toBe(before.id);

    // tìm kiếm theo từ khoá & trạng thái
    await page.getByTestId("ll-filter-q").fill("ánh sáng ngược");
    await page.getByTestId("ll-filter-status").selectOption("ROLLED_BACK");
    await expect(page.getByTestId("ll-row").filter({ hasText: title })).toBeVisible();
  });
});
