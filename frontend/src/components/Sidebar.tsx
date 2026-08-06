import { Icon } from "./Icon";

interface SidebarProps {
  onNewChat: () => void;
}

export function Sidebar({ onNewChat }: SidebarProps) {
  return <aside className="sidebar" aria-label="Chat navigation">
    <div className="brand"><span className="brand-mark"><Icon name="bot" /></span><span>MedChat</span></div>
    <button className="new-chat" type="button" onClick={onNewChat}><Icon name="plus" />New chat</button>
    <button type="button" className="account" aria-label="Open profile (not available yet)">
      <span className="avatar avatar-user"><Icon name="user" /></span><span><strong>Guest user</strong><small>Free plan</small></span><Icon name="dots" />
    </button>
  </aside>;
}
