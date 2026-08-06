export interface ChatResponse {
  answer: string;
}

export class ChatApiError extends Error {}

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, "") ?? "";

export async function sendPrompt(prompt: string): Promise<ChatResponse> {
  const response = await fetch(`${apiBaseUrl}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ prompt }),
  });

  const payload = (await response.json().catch(() => null)) as
    | ChatResponse
    | { error?: string }
    | null;

  if (!response.ok || !payload || !("answer" in payload)) {
    const message = payload && "error" in payload ? payload.error : "Unable to reach the medical assistant.";
    throw new ChatApiError(message || "Unable to reach the medical assistant.");
  }

  return payload;
}
