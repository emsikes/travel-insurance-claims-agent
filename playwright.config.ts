import { defineConfig } from "@playwright/test";
import { BACKEND_URL, DASHBOARD_URL, port } from "./urls.config";

export default defineConfig({
  testDir: "e2e",
  outputDir: "e2e/test-results",
  reporter: "list",
  use: { baseURL: DASHBOARD_URL },
  webServer: [
    {
      command: `uv run -m uvicorn backend.main:app --port ${String(port(BACKEND_URL))}`,
      url: `${BACKEND_URL}/api/health`,
      reuseExistingServer: true,
    },
    {
      command: `npx vite dashboard --port ${String(port(DASHBOARD_URL))} --strictPort`,
      url: DASHBOARD_URL,
      reuseExistingServer: true,
    },
  ],
});
