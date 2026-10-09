interface Props {
  width?: string;
  height?: string;
  radius?: string;
  className?: string;
}

/** Shimmering placeholder block shown while data loads. */
export function Skeleton({ width = "100%", height = "16px", radius, className = "" }: Props) {
  return (
    <span
      className={`skeleton ${className}`}
      style={{ width, height, borderRadius: radius }}
      aria-hidden="true"
    />
  );
}
