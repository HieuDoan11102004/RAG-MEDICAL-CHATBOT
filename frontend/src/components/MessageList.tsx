import { Icon } from "./Icon";
import type { Citation } from "../api/chat";

export interface Message {
  id: string;
  role: "user" | "assistant" | "error";
  content: string;
  citations?: Citation[];
}

export function MessageList({ messages, loading }: { messages: Message[]; loading: boolean }) {
  if (messages.length === 0 && !loading) {
    return <section className="empty-state" aria-label="Start a new conversation">
      <span className="empty-logo"><Icon name="bot" /></span>
      <h1>How can I help you today?</h1>
      <p>Ask a health question and get information from our medical knowledge base.</p>
    </section>;
  }
  return <section className="message-list" aria-live="polite" aria-label="Conversation">
    {messages.map((message) => <article key={message.id} className={`message message-${message.role}`}>
      <span className={`avatar ${message.role === "user" ? "avatar-user" : "avatar-bot"}`}><Icon name={message.role === "user" ? "user" : message.role === "error" ? "alert" : "bot"} /></span>
      <div className="message-content">
        <span className="message-label">{message.role === "user" ? "You" : message.role === "error" ? "Something went wrong" : "MedChat"}</span>
        {message.role === "assistant" ? <>
          <p>{message.content}</p>
          {message.citations && message.citations.length > 0 && <div className="citations" aria-label="Sources">
            {message.citations.map((citation) => <span key={`${citation.title}-${citation.page ?? "unknown"}`} className="citation">
              {citation.title}{citation.page === null ? "" : ` · p. ${citation.page}`}
            </span>)}
          </div>}
        </> : <p>{message.content}</p>}
      </div>
      {message.role === "assistant" && <button type="button" className="message-action" aria-label="More message options (not available yet)"><Icon name="dots" /></button>}
    </article>)}
    {loading && <article className="message message-assistant loading-message"><span className="avatar avatar-bot"><Icon name="bot" /></span><div className="message-content"><span className="message-label">MedChat</span><div className="typing" aria-label="MedChat is thinking"><i /><i /><i /></div></div></article>}
  </section>;
}
