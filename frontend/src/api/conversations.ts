const API_BASE = import.meta.env.VITE_API_BASE_URL || "";

export interface ConversationMessage {
  role: "user" | "assistant" | "error";
  content: string;
  citations?: { id: string; title: string; page: number | null }[];
}

export interface Conversation {
  id: string;
  title: string;
  created_at: string | null;
  updated_at: string | null;
}

export interface ConversationDetail extends Conversation {
  messages: ConversationMessage[];
}

export class ConversationApiError extends Error {}

async function fetchWithAuth(url: string, options: RequestInit = {}) {
  const response = await fetch(`${API_BASE}${url}`, {
    ...options,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
  });

  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new ConversationApiError(data.message || data.code || "Request failed");
  }

  return response.json();
}

export async function listConversations(): Promise<Conversation[]> {
  const data = await fetchWithAuth("/api/auth/conversations");
  return data.conversations || [];
}

export async function getConversation(id: string): Promise<ConversationDetail> {
  return fetchWithAuth(`/api/auth/conversation?id=${encodeURIComponent(id)}`);
}

export async function saveConversation(
  id: string | null,
  title: string,
  messages: ConversationMessage[]
): Promise<{ id: string; title: string }> {
  return fetchWithAuth("/api/auth/conversation", {
    method: "POST",
    body: JSON.stringify({ id, title, messages }),
  });
}

export async function deleteConversation(id: string): Promise<void> {
  await fetchWithAuth("/api/auth/conversation", {
    method: "DELETE",
    body: JSON.stringify({ id }),
  });
}
