import { sendPrompt } from "./chat";

describe("sendPrompt", () => {
  afterEach(() => vi.restoreAllMocks());

  it("posts a prompt and returns a cited answer", async () => {
    const response = { answer: "Stay hydrated.", citations: [{ id: "source-1", title: "Gale Medicine", page: 4 }] };
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify(response), { status: 200 }));
    await expect(sendPrompt("How much water?", "conversation-1")).resolves.toEqual(response);
    expect(fetchMock).toHaveBeenCalledWith("/api/messages", expect.objectContaining({ method: "POST", body: JSON.stringify({ prompt: "How much water?", conversation_id: "conversation-1" }) }));
  });

  it("throws the API message when a request fails", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ error: "Prompt is required." }), { status: 400 }));
    await expect(sendPrompt("", "conversation-1")).rejects.toMatchObject({
      name: "Error",
      message: "Prompt is required.",
    });
  });
});
