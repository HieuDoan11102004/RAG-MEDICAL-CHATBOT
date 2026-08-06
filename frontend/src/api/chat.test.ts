import { sendPrompt } from "./chat";

describe("sendPrompt", () => {
  afterEach(() => vi.restoreAllMocks());

  it("posts a prompt and returns the answer", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ answer: "Stay hydrated." }), { status: 200 }));
    await expect(sendPrompt("How much water?")).resolves.toEqual({ answer: "Stay hydrated." });
    expect(fetchMock).toHaveBeenCalledWith("/api/chat", expect.objectContaining({ method: "POST", body: JSON.stringify({ prompt: "How much water?" }) }));
  });

  it("throws the API message when a request fails", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ error: "Prompt is required." }), { status: 400 }));
    await expect(sendPrompt("")).rejects.toMatchObject({
      name: "Error",
      message: "Prompt is required.",
    });
  });
});
