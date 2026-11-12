import { loadEnv } from "vite";

const env = { ...loadEnv("", import.meta.dirname, ""), ...process.env };

export const BACKEND_URL = env.BACKEND_URL ?? "http://127.0.0.1:8000";
export const DASHBOARD_URL = env.DASHBOARD_URL ?? "http://localhost:5173";

export function port(url: string): number {
  return Number(new URL(url).port);
}
