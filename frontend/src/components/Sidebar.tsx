import { Icon } from "./Icon";
import { useAuth } from "../hooks/useAuth";

interface SidebarProps {
  onNewChat: () => void;
}

export function Sidebar({ onNewChat }: SidebarProps) {
  const { user, signOut } = useAuth();

  async function handleSignOut() {
    await signOut();
  }

  return <aside className="sidebar" aria-label="Chat navigation">
    <div className="brand"><span className="brand-mark"><Icon name="bot" /></span><span>MedChat</span></div>
    <button className="new-chat" type="button" onClick={onNewChat}><Icon name="plus" />New chat</button>
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
}
