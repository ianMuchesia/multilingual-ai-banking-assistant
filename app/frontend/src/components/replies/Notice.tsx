import { CircleQuestionMark, Ban } from "lucide-react";

interface Props {
  tone: "reject" | "rephrase";
  title: string;
  children: string;
}

/** Calm callout for unsupported requests and "not sure, please rephrase" replies. */
export function Notice({ tone, title, children }: Props) {
  const Icon = tone === "reject" ? Ban : CircleQuestionMark;
  return (
    <div className={`reply-card reply-card--${tone}`} role="note">
      <p className="reply-card__title">
        <Icon size={16} aria-hidden="true" />
        {title}
      </p>
      <p className="reply-card__body">{children}</p>
    </div>
  );
}
