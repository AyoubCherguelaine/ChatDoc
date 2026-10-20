"use client";

import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { useRouter } from "next/navigation";
import {
  clearToken,
  fetchMe,
  getToken,
  login as apiLogin,
  register as apiRegister,
  setToken,
} from "@/lib/api";
import type { User } from "@/lib/types";

interface SessionContextValue {
  user: User | null;
  loading: boolean;
  accessToken: string | null;
  login: (email: string, password: string) => Promise<void>;
  register: (name: string, email: string, password: string) => Promise<void>;
  logout: () => void;
  refresh: () => Promise<void>;
}

const SessionContext = createContext<SessionContextValue | undefined>(
  undefined,
);

export function SessionProvider({ children }: { children: ReactNode }) {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [token, setTokenState] = useState<string | null>(null);

  const loadMe = async (t: string | null) => {
    if (!t) {
      setUser(null);
      setTokenState(null);
      setLoading(false);
      return;
    }
    try {
      const me = await fetchMe();
      setUser(me);
      setTokenState(t);
    } catch {
      clearToken();
      setUser(null);
      setTokenState(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    loadMe(getToken());
  }, []);

  const doLogin = async (email: string, password: string) => {
    const res = await apiLogin({ email, password });
    setToken(res.accessToken);
    await loadMe(res.accessToken);
  };

  const doRegister = async (name: string, email: string, password: string) => {
    const res = await apiRegister({ email, name, password });
    setToken(res.accessToken);
    await loadMe(res.accessToken);
  };

  const logout = () => {
    clearToken();
    setUser(null);
    setTokenState(null);
    router.replace("/login");
  };

  return (
    <SessionContext.Provider
      value={{
        user,
        loading,
        accessToken: token,
        login: doLogin,
        register: doRegister,
        logout,
        refresh: async () => loadMe(getToken()),
      }}
    >
      {children}
    </SessionContext.Provider>
  );
}

export function useSession() {
  const ctx = useContext(SessionContext);
  if (!ctx) throw new Error("useSession must be used within SessionProvider");
  return ctx;
}

export function useRequireAuth(redirectTo = "/login") {
  const { user, loading } = useSession();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !user) {
      router.replace(redirectTo);
    }
  }, [user, loading, router, redirectTo]);

  return { user, loading };
}
