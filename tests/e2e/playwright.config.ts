import { defineConfig, devices } from "@playwright/test";

const API = process.env.E2E_API ?? "http://localhost:8100";
const WEB = process.env.E2E_WEB ?? "http://localhost:3100";
const EXTERNAL = process.env.E2E_EXTERNAL === "1";

export default defineConfig({
  testDir: "./specs",
  timeout: 120_000,
  expect: { timeout: 20_000 },
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [["list"], ["html", { open: "never" }]],
  use: { baseURL: WEB, trace: "retain-on-failure", screenshot: "only-on-failure", locale: "vi-VN", timezoneId: "Asia/Ho_Chi_Minh" },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } } },
  ],
  webServer: EXTERNAL ? undefined : [
    { command: "bash ../../scripts/e2e_api.sh", url: `${API}/health`, timeout: 120_000, reuseExistingServer: false, stdout: "pipe" },
    {
      command: "npm --prefix ../../apps/web run start -- -p 3100",
      url: `${WEB}/login`, timeout: 120_000, reuseExistingServer: false,
      env: { API_PUBLIC_URL: API, PORT: "3100" },
    },
  ],
});
