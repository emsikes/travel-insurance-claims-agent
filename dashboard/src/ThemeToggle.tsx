import { useEffect, useState } from "react";

export type Theme = "light" | "dark";

export const THEME_KEY = "undercover-theme";

function savedTheme(): Theme | null {
  try {
    const value = localStorage.getItem(THEME_KEY);
    return value === "light" || value === "dark" ? value : null;
  } catch {
    return null;
  }
}

function systemTheme(): Theme {
  return typeof window.matchMedia === "function" &&
    window.matchMedia("(prefers-color-scheme: dark)").matches
    ? "dark"
    : "light";
}

export function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>(
    () => savedTheme() ?? systemTheme(),
  );

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);

  function toggle() {
    const next: Theme = theme === "dark" ? "light" : "dark";
    setTheme(next);
    try {
      localStorage.setItem(THEME_KEY, next);
    } catch {
      // The choice still applies, it just isn't remembered.
    }
  }

  return (
    <button type="button" className="nav-button theme-toggle" onClick={toggle}>
      {theme === "dark" ? "Light Mode" : "Dark Mode"}
    </button>
  );
}
