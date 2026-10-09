// Light/dark mode, mirroring IanMuchesia/packages/theme/src/theme-mode.ts:
// the active mode is data-theme on <html>, applied before first paint by the
// inline script in index.html. Here the choice persists in localStorage
// (single origin) instead of a cross-subdomain cookie.
import { config } from "../config";

export type ThemeMode = "light" | "dark";

export const DEFAULT_THEME_MODE: ThemeMode = "light";

export function getThemeMode(): ThemeMode {
  return document.documentElement.dataset.theme === "dark" ? "dark" : DEFAULT_THEME_MODE;
}

export function setThemeMode(mode: ThemeMode): void {
  document.documentElement.dataset.theme = mode;
  try {
    localStorage.setItem(config.themeStorageKey, mode);
  } catch {
    // storage blocked: the mode still applies for this page view
  }
}
