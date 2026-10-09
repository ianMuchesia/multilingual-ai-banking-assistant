import { useBanking } from "../banking/bankingContext";
import { AiAvatar } from "../components/chat/AiAvatar";
import { ChatThread } from "../components/chat/ChatThread";
import { Composer } from "../components/chat/Composer";
import { ExampleChips } from "../components/chat/ExampleChips";
import { WelcomeState } from "../components/chat/WelcomeState";
import { brand } from "../config";
import { useHealth } from "../hooks/useHealth";

export function AssistantPage() {
  const { chat, draft, setDraft, sendMessage, openWhy, openReview } = useBanking();
  const health = useHealth();
  const empty = chat.entries.length === 0;

  return (
    <div className="page page--chat">
      <header className="chat-header">
        <AiAvatar size={40} />
        <div>
          <h1 className="chat-header__title">
            {brand.assistant} <span className="ai-badge">AI</span>
          </h1>
          <p className="label">
            {health ? `Online · ${health.router_mode} router` : "Connecting…"}
          </p>
        </div>
      </header>

      <div className="chat-card">
        <div className="chat-card__scroll">
          {empty ? (
            <WelcomeState onPick={sendMessage} disabled={chat.sending} />
          ) : (
            <ChatThread entries={chat.entries} sending={chat.sending} onWhy={openWhy} onReview={openReview} />
          )}
        </div>
        {!empty && (
          <div className="chat-card__suggestions">
            <ExampleChips onPick={sendMessage} disabled={chat.sending} />
          </div>
        )}
        <Composer value={draft} onChange={setDraft} onSend={sendMessage} disabled={chat.sending} />
      </div>
    </div>
  );
}
