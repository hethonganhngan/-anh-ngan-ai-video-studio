import { test, expect, type Page } from "@playwright/test";
import { apiAs, call, loginUI } from "../fixtures/api";

async function status(caseId: string) {
  const pm = await apiAs("pm");
  return (await call(pm, "get", `/feedback/${caseId}`)).case.status;
}

test.describe("M08 — Feedback Loop 360°", () => {
  test("đi đủ 8 bước tới CLOSED, có nhánh kiểm chứng không đạt → REOPENED", async ({ page, browser }) => {
    await loginUI(page, "qc");
    await page.goto("/feedback");
    await expect(page.getByTestId("page-title")).toHaveText("Feedback Loop 360°");
    await expect(page.getByTestId("fb-stats")).toBeVisible();

    // 1. INTAKE
    await page.getByTestId("fb-new").click();
    await page.getByTestId("fb-source").selectOption("CUSTOMER");
    await page.getByTestId("fb-category").selectOption("CHARACTER");
    await page.getByTestId("fb-title").fill("E2E khách phản ánh nhân vật đổi mặt giữa các cảnh");
    await page.getByTestId("fb-desc").fill("Bình luận Facebook: 'chị tư vấn mỗi cảnh một khuôn mặt'");
    await page.getByTestId("fb-create-submit").click();
    await page.waitForURL(/\/feedback\/[0-9a-f-]{36}/);
    const caseId = page.url().split("/").pop()!;
    expect(await status(caseId)).toBe("NEW");
    await expect(page.getByTestId("fb-stepper").locator('[data-step="INTAKE"]')).toHaveAttribute("data-state", "current");

    // 2. VALIDATE — thiếu bằng chứng bị chặn
    await page.getByTestId("fb-validate-class").selectOption("FACT");
    await page.getByTestId("fb-validate-submit").click();
    await expect(page.getByTestId("fb-action-error")).toContainText("bằng chứng");
    await page.getByTestId("fb-validate-ev-ref").first().fill("https://www.facebook.com/anhngan/posts/1#comment");
    await page.getByTestId("fb-validate-ev-note").first().fill("Ảnh chụp bình luận khách hàng");
    await page.getByTestId("fb-validate-submit").click();
    await expect(page.getByTestId("fb-triage")).toBeVisible();
    expect(await status(caseId)).toBe("VALIDATED");

    // 3. TRIAGE
    await page.getByTestId("fb-priority").selectOption("P1");
    await page.getByTestId("fb-owner").selectOption({ label: "Võ Kiểm Định (DEMO)" });
    await page.getByTestId("fb-kpi-name").fill("Tỷ lệ cảnh lệch nhân vật (%)");
    await page.getByTestId("fb-kpi-before").fill("30");
    await page.getByTestId("fb-kpi-target").fill("5");
    await page.getByTestId("fb-triage-submit").click();
    await expect(page.getByTestId("fb-rca")).toBeVisible();
    expect(await status(caseId)).toBe("RCA_PENDING");

    // 4. ROOT CAUSE — gợi ý A08 là HYPOTHESIS
    await page.getByTestId("fb-rca-suggest").click();
    await expect(page.getByTestId("fb-rca-hypothesis")).toBeVisible();
    await page.getByTestId("fb-rca-class").selectOption("FACT");
    await page.getByTestId("fb-confidence").fill("80");
    await page.getByTestId("fb-root-cause").fill("Template prompt chưa bắt buộc chèn mô tả Character Lock cố định");
    await page.getByTestId("fb-rca-submit").click();
    await expect(page.getByTestId("fb-rca-list")).toContainText("Character Lock cố định");

    // 5. CAPA — qc lập, qc tự duyệt bị chặn (không có quyền), pm duyệt
    await page.getByTestId("fb-capa-desc").fill("Thêm khối Character Lock bắt buộc vào prompt cảnh");
    await page.getByTestId("fb-capa-add").click();
    await expect(page.getByTestId("fb-capa-row")).toHaveCount(1);
    await expect(page.getByTestId("fb-capa-approve")).toHaveCount(0);
    const ctx = await browser.newContext();
    const pmPage: Page = await ctx.newPage();
    await loginUI(pmPage, "pm");
    await pmPage.goto(`/feedback/${caseId}`);
    await pmPage.getByTestId("fb-capa-approve").click();
    await expect.poll(() => status(caseId)).toBe("ACTION_APPROVED");

    // 6. ASSIGN
    await page.reload();
    await page.getByTestId("fb-start").click();
    await expect.poll(() => status(caseId)).toBe("IN_PROGRESS");
    await page.getByTestId("fb-capa-open").click();
    await page.getByTestId("fb-capa-ev-note").first().fill("Prompt v2 đã thêm khối nhân vật");
    await page.getByTestId("fb-capa-done").click();
    await expect(page.getByTestId("fb-capa-row")).toContainText("DONE");
    await page.getByTestId("fb-submit-verify").click();
    await expect(page.getByTestId("fb-verify")).toBeVisible();

    // 7. VERIFY — không đạt → REOPENED
    await page.getByTestId("fb-verify-method").fill("Tạo lại 5 video thử");
    await page.getByTestId("fb-kpi-after").fill("20");
    await page.getByTestId("fb-verify-passed").click();
    await page.getByTestId("fb-verify-ev-note").first().fill("2/10 cảnh vẫn lệch");
    await page.getByTestId("fb-verify-submit").click();
    await expect(page.getByTestId("fb-restart")).toBeVisible();
    expect(await status(caseId)).toBe("REOPENED");
    await page.getByTestId("fb-restart-target").selectOption("IN_PROGRESS");
    await page.getByTestId("fb-restart-submit").click();
    await expect.poll(() => status(caseId)).toBe("IN_PROGRESS");
    await page.getByTestId("fb-capa-open").click();
    await page.getByTestId("fb-capa-ev-note").first().fill("Bổ sung ảnh tham chiếu 3/4 vào lock");
    await page.getByTestId("fb-capa-done").click();
    await page.getByTestId("fb-submit-verify").click();
    await page.getByTestId("fb-verify-method").fill("Tạo lại 10 video thử");
    await page.getByTestId("fb-kpi-after").fill("4");
    await page.getByTestId("fb-verify-ev-note").first().fill("0/10 cảnh lệch");
    await page.getByTestId("fb-verify-submit").click();
    await expect.poll(() => status(caseId)).toBe("VERIFIED");

    // 8. STANDARDIZE & CLOSE (pm)
    await pmPage.reload();
    await pmPage.getByTestId("fb-std-note").fill("Cập nhật SOP prompt: bắt buộc khối Character Lock");
    await pmPage.getByTestId("fb-std-neg").fill("khuôn mặt khác Character Lock");
    await pmPage.getByTestId("fb-std-submit").click();
    await expect.poll(() => status(caseId)).toBe("STANDARDIZED");
    await pmPage.getByTestId("fb-close-submit").click();
    await expect.poll(() => status(caseId)).toBe("CLOSED");
    await expect(pmPage.getByTestId("fb-stepper").locator('[data-step="STANDARDIZE"]')).toHaveAttribute("data-state", "done");
    const pm = await apiAs("pm");
    const detail = await call(pm, "get", `/feedback/${caseId}`);
    expect(detail.case.kpi_after).toBe(4);
    expect(detail.case.reopen_count).toBe(1);
    expect(detail.events.map((e: any) => e.step)).toEqual(expect.arrayContaining(["INTAKE", "VALIDATE", "TRIAGE", "ROOT CAUSE", "CAPA", "ASSIGN", "VERIFY", "STANDARDIZE"]));
    const lessons = await call(pm, "get", `/lessons?q=${encodeURIComponent("nhân vật đổi mặt")}`);
    expect(lessons.items.length).toBeGreaterThan(0);
    await ctx.close();
  });
});
