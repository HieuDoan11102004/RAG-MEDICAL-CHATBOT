import "@testing-library/jest-dom/vitest";
import { vi } from "vitest";

// Store original fetch
const originalFetch = globalThis.fetch;

// Mock the auth session endpoint for all tests
beforeEach(() => {
  // Reset to original fetch first, then wrap it
  globalThis.fetch = vi.fn((url: string | URL, options?: RequestInit) => {
    const urlStr = url.toString();

    // Mock auth session endpoint
    if (urlStr.includes("/api/auth/session")) {
      return Promise.resolve(new Response(JSON.stringify({ error: "Not authenticated" }), {
        status: 401,
        headers: { "Content-Type": "application/json" }
      }));
    }

    // Let other requests pass to original fetch (for test mocks)
    return originalFetch(url, options);
  }) as typeof fetch;
});

afterEach(() => {
  vi.restoreAllMocks();
});
