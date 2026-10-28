import { test, expect } from "@playwright/test";
import { apiAs, call, createProject, loginUI } from "../fixtures/api";

test.describe("M03 — AI Script & Storyboard", () => {
  test("3 ý tưởng có điểm → chọn → viết → sửa có phiên bản → duyệt → prompt 9 phần → sửa cảnh", async ({ page }) => {
    const pm = await apiAs("pm");
    const p = await createProject(pm, { topic: "E2E M03 mẹ chọn bình sữa cho bé 1 tuổi", automation_level: "MANUAL", duration_sec: 16 });
    await loginUI(page, "pm");
    await page.goto(`/scripts?project=${p.id}`);
    await expect(page.getByTestId("page-title")).toHaveText("AI Script & Storyboard");

    await page.getByTestId("gen-ideas").click();
    for (const i of [0, 1, 2]) await expect(page.getByTestId(`idea-${i}`)).toBeVisible();
    await expect(page.getByTestId("idea-0").getByTestId("idea-score")).toHaveText(/\d+/);
    await page.getByTestId("select-idea-1").click();
    await expect(page.getByTestId("idea-1")).toContainText("Đã chọn");
    expect((await call(pm, "get", `/projects/${p.id}/script`)).script.selected_idea_index).toBe(1);

    await page.getByTestId("write-script").click();
    await expect(page.getByTestId("scene-card-1")).toBeVisible();
    await expect(page.getByTestId("script-hook")).not.toBeEmpty();

    // Chỉnh sửa: thêm câu thoại thứ 3 → bị chặn phía client
    await page.getByTestId("edit-script").click();
    const lines = await page.getByTestId("scene-editor-0").getByPlaceholder("Câu thoại").count();
    for (let k = lines; k < 3; k++) await page.getByTestId("scene-0-add-line").click();
    await expect(page.getByTestId("client-errors")).toContainText("tối đa 2 câu thoại");
    await expect(page.getByTestId("save-script")).toBeDisabled();
    // Xoá bớt để còn 1 câu và sửa nội dung
    while ((await page.getByTestId("scene-editor-0").getByLabel("Xoá thoại").count()) > 1) {
      await page.getByTestId("scene-editor-0").getByLabel("Xoá thoại").last().click();
    }
    await page.getByTestId("scene-0-line-0").fill("Mẹ ơi, bé 1 tuổi nên dùng bình sữa loại nào?");
    await page.getByTestId("version-note").fill("E2E sửa thoại cảnh 1");
    await page.getByTestId("save-script").click();
    await expect(page.getByText("Đã lưu phiên bản mới")).toBeVisible();
    const v2 = await call(pm, "get", `/projects/${p.id}/script`);
    expect(v2.current.version_no).toBe(2);
    expect(v2.scenes[0].dialogue).toHaveLength(1);
    expect(v2.scenes[0].dialogue[0].text).toBe("Mẹ ơi, bé 1 tuổi nên dùng bình sữa loại nào?");

    // Danh sách phiên bản & khôi phục v1 → v3
    await page.getByTestId("tab-versions").click();
    await expect(page.getByTestId("version-row")).toHaveCount(2);
    await page.getByTestId("restore-1").click();
    await expect(page.getByTestId("version-row")).toHaveCount(3);
    expect((await call(pm, "get", `/projects/${p.id}/script`)).current.change_note).toContain("Khôi phục từ v1");

    // Duyệt kịch bản → STORYBOARD_READY + prompt 9 phần
    await page.getByTestId("approve-comment").fill("Đạt Brand DNA");
    await page.getByTestId("approve-script").click();
    await expect(page.getByTestId("approved-note")).toBeVisible();
    expect((await call(pm, "get", `/projects/${p.id}`)).status).toBe("STORYBOARD_READY");
    await page.getByRole("tab", { name: "Kịch bản & storyboard" }).click();
    await page.getByTestId("prompt-0").locator("summary").click();
    for (const part of ["1. Loại cảnh", "5. Máy quay", "9. Negative Prompt"]) await expect(page.getByTestId("prompt-0")).toContainText(part);

    // Sửa cảnh sau duyệt → phiên bản cảnh tăng, quay lại chờ duyệt
    await page.getByTestId("edit-scene-1").click();
    await page.getByTestId("scene-action-1").fill("Tư vấn viên chỉ vào thông tin trên nhãn bình sữa");
    await page.getByTestId("save-scene-1").click();
    await expect(page.getByText("Đã lưu cảnh 2")).toBeVisible();
    const after = await call(pm, "get", `/projects/${p.id}/script`);
    expect(after.scenes[1].action).toBe("Tư vấn viên chỉ vào thông tin trên nhãn bình sữa");
    expect(after.scenes[1].current_version_no).toBeGreaterThan(1);
    expect(after.project.status).toBe("SCRIPT_REVIEW");
  });

  test("Viewer chỉ xem, không có nút tạo/duyệt", async ({ page }) => {
    const pm = await apiAs("pm");
    const p = await createProject(pm, { topic: "E2E M03 quyền xem kịch bản", automation_level: "MANUAL", duration_sec: 8 });
    await loginUI(page, "viewer");
    await page.goto(`/scripts?project=${p.id}`);
    await expect(page.getByTestId("script-status")).toBeVisible();
    await expect(page.getByTestId("gen-ideas")).toHaveCount(0);
    await expect(page.getByTestId("approve-script")).toHaveCount(0);
  });
});
