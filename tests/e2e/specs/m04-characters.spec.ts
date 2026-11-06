import { test, expect } from "@playwright/test";
import { execFileSync } from "child_process";
import { mkdtempSync } from "fs";
import { tmpdir } from "os";
import { join } from "path";
import { apiAs, call, loginUI } from "../fixtures/api";

const dir = mkdtempSync(join(tmpdir(), "e2e-m04-"));
const png = (name: string, color: string) => {
  const f = join(dir, name);
  execFileSync("ffmpeg", ["-loglevel", "error", "-y", "-f", "lavfi", "-i", `color=c=${color}:s=400x600`, "-frames:v", "1", f]);
  return f;
};
const mp3 = (name: string) => {
  const f = join(dir, name);
  execFileSync("ffmpeg", ["-loglevel", "error", "-y", "-f", "lavfi", "-i", "sine=frequency=330:duration=3", f]);
  return f;
};

test.describe("M04 — Character & Voice Studio", () => {
  test("tạo nhân vật, tải 3 ảnh, Character Lock: người tạo không tự duyệt, admin duyệt → bất biến", async ({ page }) => {
    const name = `Mẹ Lan E2E ${Date.now()}`;
    await loginUI(page, "pm");
    await page.goto("/characters");
    await page.getByTestId("new-character").click();
    await page.getByTestId("char-name").fill(name);
    await page.getByTestId("char-appearance").fill("Phụ nữ 30 tuổi, tóc ngang vai, gương mặt hiền");
    await page.getByTestId("char-outfit").fill("Áo sơ mi xanh nhạt, quần tây be");
    await page.getByTestId("char-submit").click();
    await expect(page.getByTestId("character-detail")).toBeVisible();
    await expect(page.getByTestId("char-code")).toHaveText(/CHR-\d{4}-\d{4}/);
    await expect(page.getByTestId("readiness")).toContainText("Thiếu ảnh FRONT");

    for (const [ref, color] of [["FRONT", "0x3355aa"], ["THREE_QUARTER", "0x55aa33"], ["FULL_BODY", "0xaa5533"]]) {
      await page.getByTestId(`ref-file-${ref}`).setInputFiles(png(`${ref}.png`, color));
      await expect(page.getByTestId(`ref-${ref}`)).toContainText("✓");
    }
    await expect(page.getByTestId("readiness")).toContainText("Đủ điều kiện");
    await page.getByTestId("create-lock").click();
    await expect(page.getByTestId("char-locks").getByTestId("lock-row")).toHaveCount(1);
    await expect(page.getByTestId("lock-row").first()).toHaveAttribute("data-lock-status", "DRAFT");
    // Nguyên tắc 4 mắt
    await page.getByTestId("approve-lock").click();
    await expect(page.getByText(/4 mắt/)).toBeVisible();

    const pm = await apiAs("pm");
    const ch = (await call<any[]>(pm, "get", `/characters?q=${encodeURIComponent(name)}`))[0];
    expect(ch.status).toBe("DRAFT");

    await page.getByTestId("logout").click();
    await page.waitForURL(/\/login/);
    await page.waitForLoadState("networkidle");
    await loginUI(page, "admin");
    await page.goto("/characters");
    await page.getByTestId("character-item").filter({ hasText: name }).click();
    await page.getByTestId("approve-lock").click();
    await expect(page.getByTestId("lock-row").first()).toHaveAttribute("data-lock-status", "APPROVED");
    const detail = await call<any>(pm, "get", `/characters/${ch.id}`);
    expect(detail.character.status).toBe("LOCKED");
    expect(detail.locks[0].status).toBe("APPROVED");
    expect(Object.keys(detail.locks[0].lock_data.references)).toEqual(expect.arrayContaining(["FRONT", "THREE_QUARTER", "FULL_BODY"]));
    // Lock đã duyệt không có nút sửa/duyệt lại
    await expect(page.getByTestId("approve-lock")).toHaveCount(0);
  });

  test("giọng nói có consent + audio → Voice Lock; Scene Lock tạo, duyệt và tạo phiên bản mới", async ({ page }) => {
    const vname = `Giọng Ánh Ngân E2E ${Date.now()}`;
    await loginUI(page, "admin");
    await page.goto("/characters");
    await page.getByTestId("tab-voices").click();
    await page.getByTestId("new-voice").click();
    await page.getByTestId("voice-name").fill(vname);
    await page.getByTestId("voice-accent").fill("Miền Trung (Bình Định)");
    await page.getByTestId("voice-audio-file").setInputFiles(mp3("ref.mp3"));
    await expect(page.getByText(/Đã tải/)).toBeVisible();
    await page.getByTestId("voice-consent").selectOption("GRANTED");
    await page.getByTestId("voice-submit").click();
    await expect(page.getByTestId("voice-detail")).toBeVisible();
    await page.getByTestId("create-voice-lock").click();
    await page.getByTestId("voice-locks").getByTestId("approve-lock").click();
    await expect(page.getByTestId("voice-locks").getByTestId("lock-row").first()).toHaveAttribute("data-lock-status", "APPROVED");
    const admin = await apiAs("admin");
    const v = (await call<any[]>(admin, "get", "/voices")).find((x) => x.name === vname);
    expect(v.status).toBe("LOCKED");
    expect(v.audio_reference_asset_id).toBeTruthy();
    // Sửa → lưu; Xoá phải gõ đúng mã giọng
    await page.getByTestId("voice-edit").click();
    await page.getByTestId("voice-name").fill(`${vname} sửa`);
    await page.getByTestId("voice-submit").click();
    await expect(page.getByTestId("voice-summary")).toBeVisible();
    await expect(page.getByTestId("voice-detail")).toContainText(`${vname} sửa`);
    await page.getByTestId("voice-delete").click();
    await page.getByTestId("confirm-input").fill(v.code);
    await page.getByTestId("confirm-ok").click();
    await expect(page.getByText("Đã xoá giọng nói")).toBeVisible();
    expect((await call<any[]>(admin, "get", "/voices")).some((x) => x.id === v.id)).toBe(false);

    await page.getByTestId("tab-scene-locks").click();
    const sname = `Quầy tư vấn E2E ${Date.now()}`;
    await page.getByTestId("new-scene-lock").click();
    await page.getByTestId("sl-name").fill(sname);
    await page.getByTestId("sl-setting").fill("Quầy tư vấn Ánh Ngân, kệ sữa phía sau, ánh sáng ấm");
    await page.getByTestId("sl-submit").click();
    const row = page.getByTestId("scene-lock-row").filter({ hasText: sname });
    await row.getByTestId("approve-scene-lock").click();
    await expect(row).toContainText("Đang hiệu lực");
    await row.getByTestId("new-version-scene-lock").click();
    await page.getByTestId("sl-setting").fill("Quầy tư vấn Ánh Ngân mới sơn lại màu xanh");
    await page.getByTestId("sl-submit").click();
    const locks = (await call<any[]>(admin, "get", "/scene-locks?all_versions=true")).filter((x) => x.name === sname);
    expect(locks.map((x) => x.version_no).sort()).toEqual([1, 2]);
    expect(locks.find((x) => x.version_no === 1).status).toBe("APPROVED");
    expect(locks.find((x) => x.version_no === 2).status).toBe("DRAFT");
  });
});
