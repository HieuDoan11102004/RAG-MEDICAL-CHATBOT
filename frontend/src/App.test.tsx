import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";
import App from "./App";

describe("App", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    window.sessionStorage.clear();
  });

  it("does not show fabricated recent chats", () => {
    render(<App />);
    expect(screen.queryByRole("navigation", { name: "Recent chats" })).not.toBeInTheDocument();
    expect(screen.queryByText("Understanding blood pressure")).not.toBeInTheDocument();
  });

  it("shows sent and returned messages, then clears them with New chat", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ answer: "A balanced diet can help.", citations: [{ id: "source-1", title: "The Gale Encyclopedia Of Medicine Second", page: 14 }] }), { status: 200 }));
    const user = userEvent.setup();
    render(<App />);
    await user.type(screen.getByLabelText("Ask a medical question"), "How can I eat well?");
    await user.click(screen.getByRole("button", { name: "Send message" }));
    expect(await screen.findByText("A balanced diet can help.")).toBeInTheDocument();
    expect(screen.getByText("The Gale Encyclopedia Of Medicine Second · p. 14")).toBeInTheDocument();
    expect(screen.getByText("How can I eat well?")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /new chat/i }));
    expect(screen.getByText("How can I help you today?")).toBeInTheDocument();
  });

  it("shows an inline error when the request fails", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ error: "Service unavailable" }), { status: 503 }));
    const user = userEvent.setup();
    render(<App />);
    await user.type(screen.getByLabelText("Ask a medical question"), "Hello");
    await user.click(screen.getByRole("button", { name: "Send message" }));
    expect(await screen.findByText("Service unavailable")).toBeInTheDocument();
  });

  it("keeps messages for the browser session", async () => {
    window.sessionStorage.setItem("medchat.messages", JSON.stringify([
      { id: "saved-1", role: "user", content: "Saved question" },
      { id: "saved-2", role: "assistant", content: "Saved answer" },
    ]));
    render(<App />);
    expect(screen.getByText("Saved question")).toBeInTheDocument();
    expect(screen.getByText("Saved answer")).toBeInTheDocument();
  });

  it("does not add an old reply after starting a new chat", async () => {
    let resolveRequest: (response: Response) => void;
    vi.spyOn(globalThis, "fetch").mockReturnValue(new Promise((resolve) => { resolveRequest = resolve; }));
    const user = userEvent.setup();
    render(<App />);
    await user.type(screen.getByLabelText("Ask a medical question"), "Old question");
    await user.click(screen.getByRole("button", { name: "Send message" }));
    await user.click(screen.getByRole("button", { name: /new chat/i }));
    resolveRequest!(new Response(JSON.stringify({ answer: "Late answer" }), { status: 200 }));
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(screen.queryByText("Late answer")).not.toBeInTheDocument();
  });
});
