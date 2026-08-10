import { useEffect, useRef, useState } from "react";
import { sendPrompt, type Citation } from "./api/chat";
import { getConversation, saveConversation, type ConversationMessage } from "./api/conversations";
import { AuthModal } from "./components/AuthModal";
import { Composer } from "./components/Composer";
import { Icon } from "./components/Icon";
import { MessageList, type Message } from "./components/MessageList";
import { Sidebar } from "./components/Sidebar";
import { useAuth } from "./hooks/useAuth";
import "./styles.css";

let nextMessageId = 0;
const sessionStorageKey = "medchat.messages";
const conversationStorageKey = "medchat.conversation-id";
const createMessage = (role: Message["role"], content: string, citations?: Citation[]): Message => ({ id: `message-${Date.now()}-${++nextMessageId}`, role, content, citations });

function createConversationId(): string {
  const id = crypto.randomUUID();
  window.sessionStorage.setItem(conversationStorageKey, id);
  return id;
}

function loadConversationId(): string {
  const saved = window.sessionStorage.getItem(conversationStorageKey);
  return saved || createConversationId();
}

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
  const [showAuthModal, setShowAuthModal] = useState(false);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [refreshConversations, setRefreshConversations] = useState(0);
  const conversationIdRef = useRef(loadConversationId());
  const { user, loading } = useAuth();
  const saveTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [hasSentMessage, setHasSentMessage] = useState(false); // Track if user has sent any message

  // Save messages to session storage
  useEffect(() => {
    window.sessionStorage.setItem(sessionStorageKey, JSON.stringify(messages));
  }, [messages]);

  // Auto-save conversation when messages change (debounced)
  useEffect(() => {
    // Only save if user has sent a message in this session
    if (!user || messages.length === 0 || !hasSentMessage) return;

    if (saveTimeoutRef.current) {
      clearTimeout(saveTimeoutRef.current);
    }

    saveTimeoutRef.current = setTimeout(() => {
      const convMessages: ConversationMessage[] = messages.map((m) => ({
        role: m.role as "user" | "assistant" | "error",
        content: m.content,
        citations: m.citations,
      }));

      saveConversation(activeConversationId, "", convMessages)
        .then((result) => {
          if (!activeConversationId && result.id) {
            setActiveConversationId(result.id);
            setRefreshConversations((prev) => prev + 1); // Trigger sidebar refresh
          }
        })
        .catch(() => {
          // Silently fail - saves are optional
        });
    }, 1000); // Save 1 second after last message change

    return () => {
      if (saveTimeoutRef.current) {
        clearTimeout(saveTimeoutRef.current);
      }
    };
  }, [messages, user, activeConversationId, hasSentMessage]);

  async function handleSend(prompt: string) {
    const requestConversationId = conversationIdRef.current;
    setHasSentMessage(true); // Mark that user sent a message
    setMessages((current) => [...current, createMessage("user", prompt)]);
    setIsSending(true);
    try {
      const { answer, citations } = await sendPrompt(prompt, requestConversationId);
      if (conversationIdRef.current === requestConversationId) {
        setMessages((current) => [...current, createMessage("assistant", answer, citations)]);
      }
    } catch (error) {
      const content = error instanceof Error ? error.message : "Unable to reach the medical assistant.";
      if (conversationIdRef.current === requestConversationId) {
        setMessages((current) => [...current, createMessage("error", content)]);
      }
    } finally {
      if (conversationIdRef.current === requestConversationId) setIsSending(false);
    }
  }

  function handleNewChat() {
    conversationIdRef.current = createConversationId();
    setActiveConversationId(null);
    setIsSending(false);
    setMessages([]);
    window.sessionStorage.removeItem(sessionStorageKey);
  }

  async function handleSelectConversation(id: string) {
    if (!user) return;

    try {
      const conversation = await getConversation(id);
      const loadedMessages: Message[] = conversation.messages.map((m, i) => ({
        id: `message-${Date.now()}-${++nextMessageId}-${i}`,
        role: m.role,
        content: m.content,
        citations: m.citations,
      }));

      conversationIdRef.current = id;
      setActiveConversationId(id);
      setMessages(loadedMessages);
      window.sessionStorage.setItem(sessionStorageKey, JSON.stringify(loadedMessages));
    } catch {
      // If load fails, just start new chat
      handleNewChat();
    }
  }

  function handleComposerFocus() {
    if (!user && !loading) {
      setShowAuthModal(true);
    }
  }

  // Show loading state while checking auth
  if (loading) {
    return <div className="app-shell loading">Loading...</div>;
  }

  return <div className="app-shell">
    <Sidebar
      onNewChat={handleNewChat}
      onSelectConversation={handleSelectConversation}
      activeConversationId={activeConversationId}
      refreshTrigger={refreshConversations}
    />
    <main className="chat-panel">
      <header className="topbar">
        <button type="button" className="mobile-brand" aria-label="MedChat navigation"><Icon name="bot" /></button>
        <div className="conversation-title"><strong>Medical assistant</strong><span><i /> Online</span></div>
        <div className="topbar-actions">
          {!user && (
            <button type="button" className="header-button sign-in-btn" onClick={() => setShowAuthModal(true)}>
              Sign In
            </button>
          )}
          <button type="button" className="header-button" aria-label="Search conversations (not available yet)"><Icon name="search" /></button>
          <button type="button" className="header-button" aria-label="Conversation options (not available yet)"><Icon name="dots" /></button>
        </div>
      </header>
      <div className="conversation"><MessageList messages={messages} loading={isSending} /></div>
      <div className="composer-area">
        <Composer onSend={handleSend} disabled={isSending} onFocus={handleComposerFocus} />
        <p>MedChat can make mistakes. Check important information with a healthcare professional.</p>
      </div>
    </main>
    {showAuthModal && <AuthModal onClose={() => setShowAuthModal(false)} />}
  </div>;
}
