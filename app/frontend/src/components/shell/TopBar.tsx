import { Bell } from "lucide-react";
import { Link } from "react-router-dom";
import { routes } from "../../config";
import { useHealth } from "../../hooks/useHealth";
import type { User } from "../../types/api";
import { Logo } from "../brand/Logo";
import { AvatarMenu } from "./AvatarMenu";
import { RouterModeChip } from "./RouterModeChip";
import { ThemeToggle } from "./ThemeToggle";

export function TopBar({ user, onLogout }: { user: User; onLogout: () => void }) {
  const firstName = user.full_name.trim().split(/\s+/)[0] ?? user.username;
  const health = useHealth();

  return (
    <header className="topbar">
      <div className="topbar__inner">
        <Link to={routes.home} className="topbar__brand" aria-label="Benki Yetu home">
          <Logo />
        </Link>
        <p className="topbar__greeting">
          Habari, <span className="topbar__name">{firstName}</span>
        </p>
        <div className="topbar__actions">
          <RouterModeChip health={health} />
          <ThemeToggle />
          <button type="button" className="icon-btn" aria-label="Notifications (coming soon)" title="Notifications (coming soon)">
            <Bell size={18} aria-hidden="true" />
          </button>
          <AvatarMenu user={user} onLogout={onLogout} />
        </div>
      </div>
    </header>
  );
}
