import { useEffect, useState } from "react";
import { Icon } from "./Icon";
import { useAuth } from "../hooks/useAuth";
import { listConversations, deleteConversation, type Conversation } from "../api/conversations";

interface SidebarProps {
  onNewChat: () => void;
  onSelectConversation: (id: string) => void;
  activeConversationId: string | null;
}

export function Sidebar({ onNewChat, onSelectConversation, activeConversationId }: SidebarProps) {
  const { user, signOut } = useAuth();
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (user) {
      loadConversations();
    } else {
      setConversations([]);
    }
  }, [user]);

  async function loadConversations() {
    setLoading(true);
    try {
      const convs = await listConversations();
      setConversations(convs);
    } catch {
      // Silently fail - conversations are optional
    } finally {
      setLoading(false);
    }
  }

  async function handleDeleteConversation(e: React.MouseEvent, id: string) {
    e.stopPropagation();
    try {
      await deleteConversation(id);
      setConversations((prev) => prev.filter((c) => c.id !== id));
      if (activeConversationId === id) {
        onNewChat();
      }
    } catch {
      // Silently fail
    }
  }

  return <aside className="sidebar" aria-label="Chat navigation">
    <div className="brand"><span className="brand-mark"><Icon name="bot" /></span><span>MedChat</span></div>
    <button className="new-chat" type="button" onClick={onNewChat}><Icon name="plus" />New chat</button>

    {user && (
      <div className="conversation-list">
        <div className="conversation-list-header">Recent Chats</div>
        {loading ? (
          <div className="conversation-loading">Loading...</div>
        ) : conversations.length === 0 ? (
          <div className="conversation-empty">No saved conversations</div>
        ) : (
          <ul className="conversation-items">
            {conversations.map((conv) => (
              <li key={conv.id}>
                <button
                  type="button"
                  className={`conversation-item ${activeConversationId === conv.id ? "active" : ""}`}
                  onClick={() => onSelectConversation(conv.id)}
                >
                  <span className="conversation-title">{conv.title || "New conversation"}</span>
                  <button
                    type="button"
                    className="conversation-delete"
                    onClick={(e) => handleDeleteConversation(e, conv.id)}
                    title="Delete conversation"
                  >
                    <Icon name="trash" />
                  </button>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    )}

    {user ? (
      <button type="button" className="account" aria-label="User account">
        <span className="avatar avatar-user"><Icon name="user" /></span>
        <span><strong>{user.name}</strong><small>{user.email}</small></span>
        <button type="button" className="sign-out-btn" onClick={handleSignOut} title="Sign out">
          <Icon name="dots" />
        </button>
      </button>
    ) : (
      <button type="button" className="account" aria-label="Sign in">
        <span className="avatar avatar-user"><Icon name="user" /></span>
        <span><strong>Guest user</strong><small>Sign in to save chats</small></span>
      </button>
    )}
  </aside>;

  async function handleSignOut() {
    await signOut();
    onNewChat();
  }
}
