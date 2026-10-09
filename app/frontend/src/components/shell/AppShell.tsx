import { Outlet } from "react-router-dom";
import { useAuth } from "../../auth/authContext";
import { ReviewSheet } from "../confirm/ReviewSheet";
import { WhyDrawer } from "../debug/WhyDrawer";
import { NavList } from "./NavList";
import { TopBar } from "./TopBar";

/** Signed-in layout: top bar, sidebar (desktop) or bottom tabs (phones), and the global sheets. */
export function AppShell() {
  const { session, logout } = useAuth();
  if (!session) return null;

  return (
    <div className="shell">
      <a href="#main" className="skip-link">
        Skip to content
      </a>
      <TopBar user={session.user} onLogout={logout} />
      <div className="shell__body">
        <nav className="sidebar" aria-label="Primary">
          <NavList variant="sidebar" />
        </nav>
        <main id="main" className="shell__main" tabIndex={-1}>
          <Outlet />
        </main>
      </div>
      <nav className="tabbar" aria-label="Primary">
        <NavList variant="tabbar" />
      </nav>
      <ReviewSheet />
      <WhyDrawer />
    </div>
  );
}
