import { test, expect } from "@playwright/test";
import { apiAs, call, createProject, loginUI, toFinalQC } from "../fixtures/api";

test.describe("M07 — Quality Control", () => {
  test("chấm < 98 không đạt, ≥ 98 đạt; QC reviewer không phê duyệt được; PM phê duyệt", async ({ page, browser }) => {
    const pm = await apiAs("pm");
    const p = await createProject(pm, { topic: "E2E M07 kiểm định chất lượng video" });
    await toFinalQC(pm, p.id);

    await loginUI(page, "qc");
    await page.goto("/quality");
    await expect(page.getByTestId("page-title")).toHaveText("Quality Control");
    await page.getByTestId("qc-queue-row").filter({ hasText: p.code }).getByTestId("qc-open").click();
    await expect(page.getByTestId("video-player")).toBeVisible();
    await expect(page.getByTestId("agent-suggest")).toContainText("LUFS");

    // AUTO không được vượt điểm máy đo
    const autoCap = await call(pm, "get", `/projects/${p.id}/qc`).then((v: any) => v.agent_final.scores.visual.score);
    if (autoCap < 10) {
      await page.getByTestId("score-visual").fill("10");
      await page.getByTestId("qc-submit").click();
      await expect(page.getByTestId("qc-error")).toContainText("QC_AUTO_OVERRIDE");
    }
    // Chấm 9 cho mọi tiêu chí → 90 < 98 → không đạt
    for (const k of ["hook", "script", "character", "setting", "visual", "voice", "lipsync", "audio", "brand", "compliance"]) {
      await page.getByTestId(`score-${k}`).fill(String(Math.min(9, k === "visual" || k === "audio" ? autoCap : 9)));
    }
    await page.getByTestId("qc-notes").fill("Chưa đạt chuẩn");
    await page.getByTestId("qc-submit").click();
    await expect(page.getByTestId("review-history")).toContainText("FAIL");
    expect((await call(pm, "get", `/projects/${p.id}`)).status).toBe("FINAL_QC");

    // Chấm đủ 10 (AUTO giữ trần) → đạt nếu tổng ≥ 98
    const agent = (await call(pm, "get", `/projects/${p.id}/qc`)).agent_final;
    for (const k of ["hook", "script", "character", "setting", "visual", "voice", "lipsync", "audio", "brand", "compliance"]) {
      const cap = agent.scores[k]?.method === "AUTO" ? agent.scores[k].score : 10;
      await page.getByTestId(`score-${k}`).fill(String(cap));
    }
    await expect(page.getByTestId("qc-total")).toContainText("/100");
    await page.getByTestId("qc-submit").click();
    await expect.poll(async () => (await call(pm, "get", `/projects/${p.id}`)).status).toBe("APPROVAL_PENDING");
    // QC reviewer không thấy khối phê duyệt
    await page.reload();
    await expect(page.getByTestId("release-conditions")).toBeVisible();
    await expect(page.getByTestId("approval-box")).toHaveCount(0);
    const qcApi = await apiAs("qc");
    await expect(call(qcApi, "post", `/projects/${p.id}/approve`, { decision: "APPROVED" })).rejects.toThrow(/403/);

    // PM phê duyệt qua UI
    const ctx = await browser.newContext();
    const pmPage = await ctx.newPage();
    await loginUI(pmPage, "pm");
    await pmPage.goto(`/quality?project=${p.id}`);
    await pmPage.getByTestId("approval-comment").fill("Đồng ý phát hành");
    await pmPage.getByTestId("approve-btn").click();
    await expect.poll(async () => (await call(pm, "get", `/projects/${p.id}`)).status).toBe("APPROVED");
    await ctx.close();
  });

  test("lỗi QC MAJOR chặn phát hành, tạo Feedback Case và xử lý có ghi chú", async ({ page }) => {
    const pm = await apiAs("pm");
    const p = await createProject(pm, { topic: "E2E M07 lỗi QC thủ công" });
    await toFinalQC(pm, p.id);
    await loginUI(page, "qc");
    await page.goto(`/quality?project=${p.id}`);
    const agent = (await call(pm, "get", `/projects/${p.id}/qc`)).agent_final;
    for (const k of Object.keys(agent.scores)) {
      await page.getByTestId(`score-${k}`).fill(String(agent.scores[k].method === "AUTO" ? agent.scores[k].score : 10));
    }
    await page.getByTestId("add-finding").click();
    await page.getByTestId("new-finding-severity").selectOption("MAJOR");
    await page.getByTestId("new-finding-desc").fill("Khuôn mặt nhân vật thay đổi ở cảnh 2");
    await page.getByTestId("qc-submit").click();
    const row = page.getByTestId("finding-row").filter({ hasText: "Khuôn mặt nhân vật" });
    await expect(row).toBeVisible();
    expect((await call(pm, "get", `/projects/${p.id}`)).status).toBe("FINAL_QC"); // lỗi MAJOR mở chặn phát hành
    await row.getByTestId("finding-feedback").click();
    await expect(row.getByText("Xem Feedback")).toBeVisible();
    await row.getByTestId("finding-resolve").click();
    await page.getByTestId("finding-note").fill("Đã tạo lại cảnh 2 với Character Lock v1");
    await page.getByTestId("finding-confirm").click();
    await expect(row).toContainText("Đã khắc phục");
    const f = (await call(pm, "get", `/projects/${p.id}/qc`)).findings.find((x: any) => x.description.includes("Khuôn mặt"));
    expect(f.status).toBe("RESOLVED");
    expect(f.feedback_case_id).toBeTruthy();
  });
});
