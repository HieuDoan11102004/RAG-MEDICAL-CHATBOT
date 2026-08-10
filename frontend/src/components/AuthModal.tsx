import { useState } from "react";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "";

interface AuthModalProps {
  onClose?: () => void;
}

export function AuthModal({ onClose }: AuthModalProps) {
  const [mode, setMode] = useState<"sign-in" | "sign-up">("sign-in");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      const endpoint = mode === "sign-up" ? "/api/auth/sign-up/email" : "/api/auth/sign-in/email";
      const body: Record<string, string> = { email, password };
      if (mode === "sign-up") {
        body.name = name;
        body.rememberMe = "true";
      }

      const response = await fetch(`${API_BASE}${endpoint}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify(body),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.message || data.code || "Authentication failed");
      }

      // Trigger re-render by dispatching a custom event
      window.dispatchEvent(new CustomEvent("auth-change"));
      if (onClose) onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "An error occurred");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="auth-modal-overlay">
      <div className="auth-modal">
        <button
          type="button"
          className="auth-modal-close"
          onClick={onClose}
          aria-label="Close"
        >
          ×
        </button>

        <h2>{mode === "sign-in" ? "Sign In" : "Create Account"}</h2>
        <p className="auth-subtitle">
          {mode === "sign-in"
            ? "Welcome back! Please sign in to continue."
            : "Create an account to save your conversations."}
        </p>

        <form onSubmit={handleSubmit}>
          {mode === "sign-up" && (
            <div className="auth-field">
              <label htmlFor="name">Name</label>
              <input
                id="name"
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Your name"
                required
                minLength={1}
              />
            </div>
          )}

          <div className="auth-field">
            <label htmlFor="email">Email</label>
            <input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              required
            />
          </div>

          <div className="auth-field">
            <label htmlFor="password">Password</label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder={mode === "sign-up" ? "At least 8 characters" : "Your password"}
              required
              minLength={mode === "sign-up" ? 8 : 1}
            />
          </div>

          {error && <div className="auth-error">{error}</div>}

          <button type="submit" className="auth-submit" disabled={loading}>
            {loading ? "Please wait..." : mode === "sign-in" ? "Sign In" : "Create Account"}
          </button>
        </form>

        <div className="auth-toggle">
          {mode === "sign-in" ? (
            <>
              Don't have an account?{" "}
              <button type="button" onClick={() => setMode("sign-up")}>
                Sign up
              </button>
            </>
          ) : (
            <>
              Already have an account?{" "}
              <button type="button" onClick={() => setMode("sign-in")}>
                Sign in
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
