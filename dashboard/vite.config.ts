import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";
import { BACKEND_URL, DASHBOARD_URL, port } from "../urls.config";

export default defineConfig({
  plugins: [react()],
  server: { port: port(DASHBOARD_URL), proxy: { "/api": BACKEND_URL } },
  test: {
    environment: "jsdom",
    coverage: {
      include: ["src/**"],
      exclude: ["src/main.tsx"],
      thresholds: { statements: 80 },
    },
  },
});
