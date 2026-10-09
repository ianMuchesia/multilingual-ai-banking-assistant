import { NavLink } from "react-router-dom";
import { useBanking } from "../../banking/bankingContext";
import { routes } from "../../config";
import { navItems } from "./navItems";

/** Primary navigation, rendered as a sidebar on desktop and a bottom tab bar on phones. */
export function NavList({ variant }: { variant: "sidebar" | "tabbar" }) {
  const { openAssistant } = useBanking();

  return (
    <ul className={`nav nav--${variant}`}>
      {navItems.map((item) => {
        const Icon = item.icon;
        const content = (
          <>
            <Icon size={variant === "tabbar" ? 22 : 18} aria-hidden="true" />
            <span className="nav__label">{item.label}</span>
            {item.kind === "link" && item.ai && variant === "sidebar" && <span className="ai-badge">AI</span>}
          </>
        );
        return (
          <li key={item.label}>
            {item.kind === "link" ? (
              <NavLink
                to={item.to}
                end={item.to === routes.home}
                className={({ isActive }) => `nav__item${isActive ? " nav__item--active" : ""}`}
              >
                {content}
              </NavLink>
            ) : (
              <button type="button" className="nav__item" onClick={() => openAssistant(item.prompt)}>
                {content}
              </button>
            )}
          </li>
        );
      })}
    </ul>
  );
}
