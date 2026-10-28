import { test, expect } from "@playwright/test";
import { execFileSync } from "child_process";
import { mkdtempSync } from "fs";
import { tmpdir } from "os";
import { join } from "path";
import { apiAs, call, createProject, loginUI } from "../fixtures/api";

const dir = mkdtempSync(join(tmpdir(), "e2e-m05-"));
function video(name: string, w: number, h: number, sec = 8) {
  const f = join(dir, name);
  execFileSync("ffmpeg", ["-loglevel", "error", "-y", "-f", "lavfi", "-i", `testsrc=s=${w}x${h}:d=${sec}:r=30`, "-f", "lavfi",
    "-i", `sine=frequency=500:duration=${sec}`, "-c:a", "aac", "-shortest", "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", f]);
  return f;
}

async function storyboard(pm: any, over: Record<string, unknown> = {}) {
  const p = await createProject(pm, { automation_level: "MANUAL", duration_sec: 16, ...over });
  await call(pm, "post", `/projects/${p.id}/script/ideas`);
  await call(pm, "post", `/projects/${p.id}/script/select-idea`, { index: 0 });
  await call(pm, "post", `/projects/${p.id}/script/write`);
  await call(pm, "post", `/projects/${p.id}/script/approve`, { comment: "E2E" });
  return p;
}

test.describe("M05 — Video Production", () => {
  test("kiểm tra tài nguyên → tạo cảnh Mock → nhập Flow (hợp lệ & sai tỉ lệ) → tạo lại cảnh → QC cảnh", async ({ page }) => {
    const pm = await apiAs("pm");
    const p = await storyboard(pm, { topic: "E2E M05 sản xuất cảnh tư vấn tã" });
    await loginUI(page, "pm");
    await page.goto(`/production?project=${p.id}`);
    await expect(page.getByTestId("providers")).toContainText("Mock Provider (DEMO");
    await expect(page.getByTestId("provider-manual_flow")).toContainText("Manual Flow Import");

    await page.getByTestId("validate-assets").click();
    await expect(page.getByTestId("asset-report")).toContainText("Đủ điều kiện tạo cảnh");
    expect((await call(pm, "get", `/projects/${p.id}`)).status).toBe("GENERATION_QUEUED");

    await page.getByTestId("generate").click();
    await expect(page.getByText(/Đã gửi 2 tác vụ/)).toBeVisible();
    await expect.poll(async () => (await call(pm, "get", `/projects/${p.id}`)).status, { timeout: 60_000 }).toBe("SCENE_QC");
    await page.reload();
    await expect(page.getByTestId("prod-scene-0").getByTestId("video-player")).toBeVisible();

    // Flow: file sai tỉ lệ bị từ chối
    await page.getByTestId("import-flow-0").click();
    await page.getByTestId("flow-file").setInputFiles(video("ngang.mp4", 1280, 720));
    await page.getByTestId("flow-submit").click();
    await expect(page.getByTestId("flow-errors")).toContainText("không phải 9:16");
    await page.keyboard.press("Escape");
    // Flow: file hợp lệ được nhận và gắn vào cảnh
    await page.getByTestId("import-flow-0").click();
    await page.getByTestId("flow-file").setInputFiles(video("doc.mp4", 720, 1280));
    await page.getByTestId("flow-submit").click();
    await expect(page.getByText(/Đã nhập cảnh 1 từ Flow/)).toBeVisible();
    let rows = await call<any[]>(pm, "get", `/projects/${p.id}/production`);
    const sel = rows[0].outputs.find((a: any) => a.id === rows[0].scene.selected_asset_id);
    expect(sel.source).toBe("MANUAL_FLOW");
    expect(rows[0].outputs.length).toBe(2);
    expect(rows[0].jobs.some((j: any) => j.provider_code === "manual_flow" && j.status === "SUCCEEDED")).toBeTruthy();

    // Tạo lại cảnh 2
    await page.getByTestId("regen-1").click();
    await expect(page.getByText(/Đã xếp hàng tạo lại cảnh 2/)).toBeVisible();
    await expect.poll(async () => {
      const r = await call<any[]>(pm, "get", `/projects/${p.id}/production`);
      return r[1].jobs.filter((j: any) => j.status === "SUCCEEDED").length;
    }, { timeout: 60_000 }).toBe(2);
    await page.reload();
    await expect(page.getByTestId("prod-scene-1").getByTestId("attempts")).toContainText("Lần 2/4");

    // QC thủ công: cảnh 1 không đạt
    await page.getByTestId("scene-qc-0").click();
    await page.getByTestId("qc-fail").check();
    await page.getByTestId("qc-notes").fill("Khuôn mặt nhân vật khác cảnh 2");
    await page.getByTestId("qc-submit").click();
    await expect(page.getByText(/KHÔNG ĐẠT/)).toBeVisible();
    rows = await call<any[]>(pm, "get", `/projects/${p.id}/production`);
    expect(rows[0].scene.status).toBe("QC_FAILED");
  });

  test("vượt ngân sách dự án → bị chặn ở kiểm tra tài nguyên và khi tạo cảnh", async ({ page }) => {
    const pm = await apiAs("pm");
    // Lớp 1: kiểm tra tài nguyên phát hiện vượt ngân sách → không cho tạo cảnh
    const p = await storyboard(pm, { topic: "E2E M05 ngân sách thấp", budget_limit: 10000 });
    await loginUI(page, "pm");
    await page.goto(`/production?project=${p.id}`);
    await page.getByTestId("validate-assets").click();
    await expect(page.getByTestId("asset-report")).toContainText("VƯỢT");
    await expect(page.getByTestId("project-error")).toContainText("ngân sách");
    expect((await call<any[]>(pm, "get", `/projects/${p.id}/production`)).every((r: any) => r.jobs.length === 0)).toBeTruthy();
    // Lớp 2: ngân sách bị giảm SAU khi đã kiểm tra → lệnh tạo cảnh bị chặn cứng
    const p2 = await storyboard(pm, { topic: "E2E M05 ngân sách bị giảm", budget_limit: 500000 });
    await call(pm, "post", `/projects/${p2.id}/validate-assets`);
    await call(pm, "patch", `/projects/${p2.id}`, { budget_limit: 10000 });
    await page.goto(`/production?project=${p2.id}`);
    await page.getByTestId("generate").click();
    await expect(page.getByTestId("budget-error")).toContainText("Vượt ngân sách");
    expect((await call<any[]>(pm, "get", `/projects/${p2.id}/production`)).every((r: any) => r.jobs.length === 0)).toBeTruthy();
  });
});
