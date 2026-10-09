import { TriangleAlert } from "lucide-react";
import { useEffect, useRef } from "react";
import type { ChatEntry } from "../../types/chat";
import { AiAvatar } from "./AiAvatar";
import { AssistantMessage } from "./AssistantMessage";

interface Props {
  entries: ChatEntry[];
  sending: boolean;
  onWhy: (entryId: string) => void;
  onReview: (entryId: string) => void;
}

export function ChatThread({ entries, sending, onWhy, onReview }: Props) {
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    endRef.current?.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "end" });
  }, [entries.length, sending]);

  return (
    <>
      <ol className="thread" aria-live="polite" aria-relevant="additions" aria-label="Conversation">
        {entries.map((entry) => {
          if (entry.role === "user") {
            return (
              <li key={entry.id} className="msg msg--user">
                <div className="bubble bubble--user">
                  <p className="bubble__text">{entry.text}</p>
                </div>
              </li>
            );
          }
          if (entry.role === "error") {
            return (
              <li key={entry.id} className="msg msg--assistant">
                <AiAvatar />
                <div className="bubble bubble--error" role="alert">
                  <TriangleAlert size={16} aria-hidden="true" />
                  <p className="bubble__text">{entry.text}</p>
                </div>
              </li>
            );
          }
          return (
            <AssistantMessage
              key={entry.id}
              entry={entry}
              onWhy={() => onWhy(entry.id)}
              onReview={() => onReview(entry.id)}
            />
          );
        })}
        {sending && (
          <li className="msg msg--assistant">
            <AiAvatar />
            <div className="bubble bubble--assistant typing">
              <span className="visually-hidden">Benki AI is typing</span>
              <span className="typing__dot" aria-hidden="true" />
              <span className="typing__dot" aria-hidden="true" />
              <span className="typing__dot" aria-hidden="true" />
            </div>
          </li>
        )}
      </ol>
      <div ref={endRef} />
    </>
  );
}
