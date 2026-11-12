import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { THEME_KEY, ThemeToggle } from "./ThemeToggle";

function systemPrefersDark(dark: boolean) {
  vi.stubGlobal(
    "matchMedia",
    vi.fn((query: string) => ({ matches: dark, media: query })),
  );
}

beforeEach(() => {
  localStorage.clear();
  delete document.documentElement.dataset.theme;
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

it("starts in light mode when the system has no preference", () => {
  render(<ThemeToggle />);
  expect(document.documentElement.dataset.theme).toBe("light");
  expect(screen.getByText("Dark Mode")).toBeDefined();
});

it("follows the system's dark mode until the handler picks", () => {
  systemPrefersDark(true);
  render(<ThemeToggle />);
  expect(document.documentElement.dataset.theme).toBe("dark");
  expect(screen.getByText("Light Mode")).toBeDefined();
});

it("switches between light and dark and remembers the choice", () => {
  render(<ThemeToggle />);
  fireEvent.click(screen.getByText("Dark Mode"));
  expect(document.documentElement.dataset.theme).toBe("dark");
  expect(localStorage.getItem(THEME_KEY)).toBe("dark");

  fireEvent.click(screen.getByText("Light Mode"));
  expect(document.documentElement.dataset.theme).toBe("light");
  expect(localStorage.getItem(THEME_KEY)).toBe("light");
});

it("uses a saved choice over the system's", () => {
  systemPrefersDark(true);
  localStorage.setItem(THEME_KEY, "light");
  render(<ThemeToggle />);
  expect(document.documentElement.dataset.theme).toBe("light");
});

it("still switches when the browser blocks storage", () => {
  vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
    throw new Error("blocked");
  });
  vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
    throw new Error("blocked");
  });
  render(<ThemeToggle />);
  fireEvent.click(screen.getByText("Dark Mode"));
  expect(document.documentElement.dataset.theme).toBe("dark");
});
