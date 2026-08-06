import { useEffect, useRef, useState } from "react";
import { sendPrompt, type Citation } from "./api/chat";
import { Composer } from "./components/Composer";
import { Icon } from "./components/Icon";
import { MessageList, type Message } from "./components/MessageList";
import { Sidebar } from "./components/Sidebar";
import "./styles.css";

let nextMessageId = 0;
const sessionStorageKey = "medchat.messages";
const createMessage = (role: Message["role"], content: string, citations?: Citation[]): Message => ({ id: `message-${Date.now()}-${++nextMessageId}`, role, content, citations });

function loadMessages(): Message[] {
  try {
    const saved = window.sessionStorage.getItem(sessionStorageKey);
    const parsed: unknown = saved ? JSON.parse(saved) : [];
    if (!Array.isArray(parsed)) return [];
    return parsed.filter((message): message is Message =>
      typeof message === "object" && message !== null &&
      typeof message.id === "string" &&
      typeof message.content === "string" &&
      (message.citations === undefined || Array.isArray(message.citations)) &&
      ["user", "assistant", "error"].includes(message.role as string),
    );
  } catch {
    return [];
  }
}

export default function App() {
  const [messages, setMessages] = useState<Message[]>(loadMessages);
  const [isSending, setIsSending] = useState(false);
  const conversationId = useRef(0);

  useEffect(() => {
    window.sessionStorage.setItem(sessionStorageKey, JSON.stringify(messages));
  }, [messages]);

  async function handleSend(prompt: string) {
    const requestConversationId = conversationId.current;
    setMessages((current) => [...current, createMessage("user", prompt)]);
    setIsSending(true);
    try {
      const { answer, citations } = await sendPrompt(prompt);
      if (conversationId.current === requestConversationId) {
        setMessages((current) => [...current, createMessage("assistant", answer, citations)]);
      }
    } catch (error) {
      const content = error instanceof Error ? error.message : "Unable to reach the medical assistant.";
      if (conversationId.current === requestConversationId) {
        setMessages((current) => [...current, createMessage("error", content)]);
      }
    } finally {
      if (conversationId.current === requestConversationId) setIsSending(false);
    }
  }

  function handleNewChat() {
    conversationId.current += 1;
    setIsSending(false);
    setMessages([]);
    window.sessionStorage.removeItem(sessionStorageKey);
  }

  return <div className="app-shell">
    <Sidebar onNewChat={handleNewChat} />
    <main className="chat-panel">
      <header className="topbar">
        <button type="button" className="mobile-brand" aria-label="MedChat navigation"><Icon name="bot" /></button>
        <div className="conversation-title"><strong>Medical assistant</strong><span><i /> Online</span></div>
        <div className="topbar-actions">
          <button type="button" className="header-button" aria-label="Search conversations (not available yet)"><Icon name="search" /></button>
          <button type="button" className="header-button" aria-label="Conversation options (not available yet)"><Icon name="dots" /></button>
        </div>
      </header>
      <div className="conversation"><MessageList messages={messages} loading={isSending} /></div>
      <div className="composer-area"><Composer onSend={handleSend} disabled={isSending} /><p>MedChat can make mistakes. Check important information with a healthcare professional.</p></div>
    </main>
  </div>;
}
