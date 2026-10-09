import { Sparkles } from "lucide-react";

export function AiAvatar({ size = 32 }: { size?: number }) {
  return (
    <span className="ai-avatar" style={{ width: size, height: size }} aria-hidden="true">
      <Sparkles size={Math.round(size * 0.5)} />
    </span>
  );
}
