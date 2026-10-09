import { useCallback, useState } from "react";
import { getThemeMode, setThemeMode, type ThemeMode } from "./themeMode";

export function useThemeMode(): { mode: ThemeMode; toggle: () => void } {
  const [mode, setMode] = useState<ThemeMode>(getThemeMode);

  const toggle = useCallback(() => {
    const next: ThemeMode = getThemeMode() === "dark" ? "light" : "dark";
    setThemeMode(next);
    setMode(next);
  }, []);

  return { mode, toggle };
}
