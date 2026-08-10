import { useState, useEffect, useCallback } from "react";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "";

export interface User {
  id: string;
  email: string;
  name: string;
  image?: string | null;
  email_verified: boolean;
  created_at: string;
  updated_at: string;
}

export interface Session {
  session: {
    id: string;
    token: string;
    expires_at: string;
    user_id: string;
  };
  user: User;
}

export function useAuth() {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchSession = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/api/auth/session`, {
        credentials: "include",
      });

      if (response.ok) {
        const data: Session = await response.json();
        setUser(data.user);
      } else {
        setUser(null);
      }
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchSession();

    // Listen for auth changes
    const handleAuthChange = () => fetchSession();
    window.addEventListener("auth-change", handleAuthChange);
    return () => window.removeEventListener("auth-change", handleAuthChange);
  }, [fetchSession]);

  const signOut = useCallback(async () => {
    try {
      await fetch(`${API_BASE}/api/auth/sign-out`, {
        method: "POST",
        credentials: "include",
      });
    } finally {
      setUser(null);
      window.dispatchEvent(new CustomEvent("auth-change"));
    }
  }, []);

  return { user, loading, signOut, refetch: fetchSession };
}
