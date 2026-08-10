import { render, screen, act, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";
import App from "./App";

describe("App", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    window.sessionStorage.clear();
  });

  it("does not show fabricated recent chats", async () => {
    const fetchMock = vi.fn((url: string | URL) => {
      const urlStr = url.toString();
      if (urlStr.includes("/api/auth/session")) {
        return Promise.resolve(new Response(JSON.stringify({ error: "Not authenticated" }), { status: 401 }));
      }
      return Promise.reject(new Error("Unexpected fetch"));
    });
    globalThis.fetch = fetchMock as typeof fetch;

    render(<App />);
    await waitFor(() => {
      expect(screen.queryByText("Loading...")).not.toBeInTheDocument();
    });
    expect(screen.queryByRole("navigation", { name: "Recent chats" })).not.toBeInTheDocument();
    expect(screen.queryByText("Understanding blood pressure")).not.toBeInTheDocument();
  });

  it("shows sent and returned messages, then clears them with New chat", async () => {
    const response = { answer: "A balanced diet can help.", citations: [{ id: "source-1", title: "The Gale Encyclopedia Of Medicine Second", page: 14 }] };
    const fetchMock = vi.fn((url: string | URL) => {
      const urlStr = url.toString();
      if (urlStr.includes("/api/auth/session")) {
        return Promise.resolve(new Response(JSON.stringify({ error: "Not authenticated" }), { status: 401 }));
      }
      return Promise.resolve(new Response(JSON.stringify(response), { status: 200 }));
    });
    globalThis.fetch = fetchMock as typeof fetch;

    const user = userEvent.setup();
    render(<App />);
    await waitFor(() => {
      expect(screen.queryByText("Loading...")).not.toBeInTheDocument();
    });

    const firstConversationId = window.sessionStorage.getItem("medchat.conversation-id");
    await user.type(screen.getByLabelText("Ask a medical question"), "How can I eat well?");
    await user.click(screen.getByRole("button", { name: "Send message" }));
    expect(await screen.findByText("A balanced diet can help.")).toBeInTheDocument();
    expect(screen.getByText("The Gale Encyclopedia Of Medicine Second · p. 14")).toBeInTheDocument();
    expect(screen.getByText("How can I eat well?")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining("/api/messages"), expect.objectContaining({
      body: JSON.stringify({ prompt: "How can I eat well?", conversation_id: firstConversationId }),
    }));
    await user.click(screen.getByRole("button", { name: /new chat/i }));
    expect(screen.getByText("How can I help you today?")).toBeInTheDocument();
    expect(window.sessionStorage.getItem("medchat.conversation-id")).not.toBe(firstConversationId);
  });

  it("shows an inline error when the request fails", async () => {
    const fetchMock = vi.fn((url: string | URL) => {
      const urlStr = url.toString();
      if (urlStr.includes("/api/auth/session")) {
        return Promise.resolve(new Response(JSON.stringify({ error: "Not authenticated" }), { status: 401 }));
      }
      return Promise.resolve(new Response(JSON.stringify({ error: "Service unavailable" }), { status: 503 }));
    });
    globalThis.fetch = fetchMock as typeof fetch;

    const user = userEvent.setup();
    render(<App />);
    await waitFor(() => {
      expect(screen.queryByText("Loading...")).not.toBeInTheDocument();
    });

    await user.type(screen.getByLabelText("Ask a medical question"), "Hello");
    await user.click(screen.getByRole("button", { name: "Send message" }));
    expect(await screen.findByText("Service unavailable")).toBeInTheDocument();
  });

  it("keeps messages for the browser session", async () => {
    const fetchMock = vi.fn((url: string | URL) => {
      const urlStr = url.toString();
      if (urlStr.includes("/api/auth/session")) {
        return Promise.resolve(new Response(JSON.stringify({ error: "Not authenticated" }), { status: 401 }));
      }
      return Promise.resolve(new Response(JSON.stringify({ answer: "Late answer" }), { status: 200 }));
    });
    globalThis.fetch = fetchMock as typeof fetch;

    window.sessionStorage.setItem("medchat.messages", JSON.stringify([
      { id: "saved-1", role: "user", content: "Saved question" },
      { id: "saved-2", role: "assistant", content: "Saved answer" },
    ]));
    render(<App />);
    await waitFor(() => {
      expect(screen.queryByText("Loading...")).not.toBeInTheDocument();
    });
    expect(screen.getByText("Saved question")).toBeInTheDocument();
    expect(screen.getByText("Saved answer")).toBeInTheDocument();
  });

  it("does not add an old reply after starting a new chat", async () => {
    let resolveRequest: (response: Response) => void;
    const fetchMock = vi.fn((url: string | URL) => {
      const urlStr = url.toString();
      if (urlStr.includes("/api/auth/session")) {
        return Promise.resolve(new Response(JSON.stringify({ error: "Not authenticated" }), { status: 401 }));
      }
      return new Promise((resolve) => { resolveRequest = resolve; });
    });
    globalThis.fetch = fetchMock as typeof fetch;

    const user = userEvent.setup();
    render(<App />);
    await waitFor(() => {
      expect(screen.queryByText("Loading...")).not.toBeInTheDocument();
    });

    await user.type(screen.getByLabelText("Ask a medical question"), "Old question");
    await user.click(screen.getByRole("button", { name: "Send message" }));
    await user.click(screen.getByRole("button", { name: /new chat/i }));
    resolveRequest!(new Response(JSON.stringify({ answer: "Late answer" }), { status: 200 }));
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(screen.queryByText("Late answer")).not.toBeInTheDocument();
  });
});
