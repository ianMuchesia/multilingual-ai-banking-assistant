import { Moon, Sun } from "lucide-react";
import { useThemeMode } from "../../theme/useThemeMode";

export function ThemeToggle() {
  const { mode, toggle } = useThemeMode();
  const next = mode === "dark" ? "light" : "dark";
  return (
    <button type="button" className="icon-btn" onClick={toggle} aria-label={`Switch to ${next} mode`} title={`Switch to ${next} mode`}>
      {mode === "dark" ? <Sun size={18} aria-hidden="true" /> : <Moon size={18} aria-hidden="true" />}
    </button>
  );
}
