import { CircleQuestionMark } from "lucide-react";
import type { AssistantEntry } from "../../types/chat";
import { ActionSummary } from "../confirm/ActionSummary";
import { RouteBadge } from "../debug/RouteBadge";
import { ReplyBody } from "../replies/ReplyBody";
import { AiAvatar } from "./AiAvatar";

interface Props {
  entry: AssistantEntry;
  onWhy: () => void;
  onReview: () => void;
}

export function AssistantMessage({ entry, onWhy, onReview }: Props) {
  const { reply, decision, pending_action } = entry.response;

  return (
    <li className="msg msg--assistant">
      <AiAvatar />
      <div className="msg__body">
        <div className="bubble bubble--assistant">
          {reply.text && <p className="bubble__text">{reply.text}</p>}
          <ReplyBody reply={reply} />
          {pending_action && <ActionSummary entry={entry} action={pending_action} onReview={onReview} />}
        </div>
        <div className="msg__meta">
          <RouteBadge route={decision.route} />
          <button type="button" className="why-btn" onClick={onWhy}>
            <CircleQuestionMark size={14} aria-hidden="true" />
            Why this answer?
          </button>
        </div>
      </div>
    </li>
  );
}
