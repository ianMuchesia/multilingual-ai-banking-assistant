import { brand } from "../../config";

/**
 * Benki Yetu mark: a bank pediment drawn in currentColor (charcoal / soft ivory)
 * with the entablature band in --brand amber, so it recolours with the theme.
 */
export function LogoMark({ size = 28 }: { size?: number }) {
  return (
    <svg
      className="logo-mark"
      width={size}
      height={size}
      viewBox="0 0 32 32"
      aria-hidden="true"
      focusable="false"
    >
      <path d="M4 12 16 4l12 8z" fill="currentColor" />
      <rect x="4" y="13" width="24" height="3" style={{ fill: "var(--brand)" }} />
      <path d="M7 17h3v8H7zm7.5 0h3v8h-3zM22 17h3v8h-3zM4 26h24v2.5H4z" fill="currentColor" />
    </svg>
  );
}

export function Logo({ size = 28, showWordmark = true }: { size?: number; showWordmark?: boolean }) {
  return (
    <span className="logo">
      <LogoMark size={size} />
      {showWordmark ? (
        <span className="logo__word">{brand.name}</span>
      ) : (
        <span className="visually-hidden">{brand.name}</span>
      )}
    </span>
  );
}
