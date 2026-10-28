/** Helper gọi API trực tiếp để dựng trạng thái nghiệp vụ trước khi kiểm thử UI. */
import { request, type APIRequestContext, type Page, expect } from "@playwright/test";

export const API = process.env.E2E_API ?? "http://localhost:8100";
export const USERS: Record<string, [string, string]> = {
  admin: ["admin@anhngan.local", "Admin@12345678"],
  pm: ["pm@anhngan.local", "Demo@12345678"],
  sysadmin: ["sysadmin@anhngan.local", "Demo@12345678"],
  creator: ["creator@anhngan.local", "Demo@12345678"],
  editor: ["editor@anhngan.local", "Demo@12345678"],
  qc: ["qc@anhngan.local", "Demo@12345678"],
  publisher: ["publisher@anhngan.local", "Demo@12345678"],
  viewer: ["viewer@anhngan.local", "Demo@12345678"],
};
export type Role = keyof typeof USERS;

const tokens: Record<string, string> = {};

export async function apiAs(role: Role): Promise<APIRequestContext> {
  if (!tokens[role]) {
    const ctx = await request.newContext({ baseURL: API });
    const r = await ctx.post("/api/v1/auth/login", { data: { email: USERS[role][0], password: USERS[role][1] } });
    expect(r.ok(), await r.text()).toBeTruthy();
    tokens[role] = (await r.json()).access_token;
    await ctx.dispose();
  }
  return request.newContext({ baseURL: `${API}/api/v1/`, extraHTTPHeaders: { Authorization: `Bearer ${tokens[role]}` } });
}

export async function call<T = any>(ctx: APIRequestContext, method: "get" | "post" | "put" | "patch" | "delete", url: string, data?: unknown): Promise<T> {
  const r = await ctx[method](url.replace(/^\//, ""), data !== undefined ? { data } : undefined);
  const body = await r.text();
  if (!r.ok()) throw new Error(`${method.toUpperCase()} ${url} → ${r.status()}: ${body}`);
  return (body ? JSON.parse(body) : null) as T;
}

/** Đăng nhập trên trình duyệt (cookie httpOnly do API đặt, dùng chung host localhost). */
export async function loginUI(page: Page, role: Role) {
  await page.goto("/login");
  await page.getByTestId("login-email").fill(USERS[role][0]);
  await page.getByTestId("login-password").fill(USERS[role][1]);
  await page.getByTestId("login-submit").click();
  await page.waitForURL((u) => !u.pathname.startsWith("/login"));
}

export async function channels(ctx: APIRequestContext): Promise<Record<string, { id: string; code: string; name: string }>> {
  const list = await call<any[]>(ctx, "get", "/channels");
  return Object.fromEntries(list.map((c) => [c.code, c]));
}

export async function createProject(ctx: APIRequestContext, over: Record<string, unknown> = {}) {
  const ch = await channels(ctx);
  const res = await call<any>(ctx, "post", "/projects", {
    channel_id: ch.ANNGAN.id, topic: "Hướng dẫn mẹ chọn tã cho bé mùa nóng", duration_sec: 16,
    automation_level: "ASSISTED", cta: "Ghé Ánh Ngân để được tư vấn nhé", ...over,
  });
  return res.projects[0];
}

export async function toStoryboard(pm: APIRequestContext, pid: string) {
  await call(pm, "post", `/projects/${pid}/script/ideas`);
  await call(pm, "post", `/projects/${pid}/script/write`);
  await call(pm, "post", `/projects/${pid}/script/approve`, { comment: "E2E" });
}

/** ASSISTED: tạo cảnh Mock → QC cảnh → render → FINAL_QC */
export async function toFinalQC(pm: APIRequestContext, pid: string) {
  await toStoryboard(pm, pid);
  await call(pm, "post", `/projects/${pid}/validate-assets`);
  await call(pm, "post", `/projects/${pid}/generate`, {});
  const p = await call<any>(pm, "get", `/projects/${pid}`);
  expect(p.status).toBe("FINAL_QC");
}

export const SCORES = (s = 10, over: Record<string, number> = {}) =>
  Object.fromEntries(["hook", "script", "character", "setting", "visual", "voice", "lipsync", "audio", "brand", "compliance"]
    .map((k) => [k, { score: over[k] ?? s, note: "" }]));

export async function toApproved(pid: string) {
  const pm = await apiAs("pm");
  const qc = await apiAs("qc");
  await toFinalQC(pm, pid);
  await call(qc, "post", `/projects/${pid}/qc/final`, { scores: SCORES(10), notes: "E2E đạt" });
  await call(pm, "post", `/projects/${pid}/approve`, { decision: "APPROVED", comment: "E2E" });
}
