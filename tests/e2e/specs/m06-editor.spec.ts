import { test, expect } from "@playwright/test";
import { execFileSync } from "child_process";
import { mkdtempSync } from "fs";
import { tmpdir } from "os";
import { join } from "path";
import { apiAs, call, createProject, loginUI, toFinalQC } from "../fixtures/api";

const dir = mkdtempSync(join(tmpdir(), "e2e-m06-"));

test.describe("M06 — AI Video Editor", () => {
  test("sắp xếp cảnh, cắt đoạn, nhạc nền, lưu timeline và Export MP4 thật", async ({ page }) => {
    test.setTimeout(240_000);
    const pm = await apiAs("pm");
    const p = await createProject(pm, { topic: "E2E M06 dựng video tư vấn sữa", duration_sec: 16 });
    await toFinalQC(pm, p.id);
    const before = await call<any[]>(pm, "get", `/projects/${p.id}/renders`);
    expect(before).toHaveLength(1);
    const tl0 = await call<any>(pm, "get", `/projects/${p.id}/timeline`);

    await loginUI(page, "editor");
    await page.goto(`/editor?project=${p.id}`);
    await expect(page.getByTestId("page-title")).toHaveText("AI Video Editor");
    await expect(page.getByTestId("render-item")).toHaveCount(1);

    // Đổi thứ tự: cảnh 2 lên đầu
    await page.getByTestId("clip-down-0").click();
    await expect(page.getByTestId("clip-title-0")).toContainText("Cảnh 2");
    // Cắt đoạn vượt thời lượng → lỗi; sửa thành 5s
    await page.getByTestId("trim-end-0").fill("99");
    await expect(page.getByTestId("timeline-errors")).toContainText("vượt thời lượng clip");
    await expect(page.getByTestId("export-mp4")).toBeDisabled();
    await page.getByTestId("trim-end-0").fill("5");
    await expect(page.getByTestId("timeline-errors")).toHaveCount(0);

    // Tải nhạc nền và bật
    const mp3 = join(dir, "nhac-nen.mp3");
    execFileSync("ffmpeg", ["-loglevel", "error", "-y", "-f", "lavfi", "-i", "sine=frequency=220:duration=6", mp3]);
    await page.getByTestId("music").locator("..").getByTestId("upload-file").setInputFiles(mp3);
    await page.getByTestId("upload-submit").click();
    await expect(page.getByText(/Đã tải lên/)).toBeVisible();
    await page.getByTestId("music-toggle").click();
    await page.getByTestId("music-asset").selectOption({ label: "nhac-nen.mp3" });
    await page.getByTestId("thumb-title").fill("Chọn sữa cho bé");

    await page.getByTestId("save-timeline").click();
    await expect(page.getByText("Đã lưu timeline")).toBeVisible();
    const tl = await call<any>(pm, "get", `/projects/${p.id}/timeline`);
    expect(tl.clips[0].scene_id).toBe(tl0.clips[1].scene_id);
    expect(tl.clips[0].trim_end).toBe(5);
    expect(tl.music?.asset_id).toBeTruthy();
    expect(tl.thumbnail.title).toBe("Chọn sữa cho bé");

    await page.getByTestId("export-mp4").click();
    await expect(page.getByText("Đã gửi render MP4")).toBeVisible();
    await expect.poll(async () => (await call<any[]>(pm, "get", `/projects/${p.id}/renders`)).length, { timeout: 120_000 }).toBe(2);
    const renders = await call<any[]>(pm, "get", `/projects/${p.id}/renders`);
    const r = renders[0];
    expect(r.version_no).toBe(2);
    expect(r.video_asset_id).toBeTruthy();
    expect(r.width).toBe(540);
    expect(r.height).toBe(960);
    expect(r.duration_sec).toBeGreaterThan(12.5);
    expect(r.duration_sec).toBeLessThan(13.5);
    expect(r.probe.has_audio).toBeTruthy();
    const mp4 = await pm.get(`assets/${r.video_asset_id}/content`);
    expect((await mp4.body()).subarray(4, 8).toString()).toBe("ftyp");
    await page.reload();
    await expect(page.getByTestId("render-item")).toHaveCount(2);
    await expect(page.getByTestId("render-item").first().getByTestId("download-mp4")).toBeVisible();
  });
});
