import { BookOpen } from "lucide-react";
import type { TransferHelpData } from "../../types/api";
import { humanize } from "../../utils/format";

export function FaqReply({ data }: { data: TransferHelpData }) {
  return (
    <aside className="reply-card reply-card--faq">
      <p className="reply-card__title">
        <BookOpen size={16} aria-hidden="true" />
        {humanize(data.topic)}
      </p>
      <p className="reply-card__body">{data.answer}</p>
    </aside>
  );
}
