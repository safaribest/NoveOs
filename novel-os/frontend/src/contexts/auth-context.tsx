import { useEffect, useState, useCallback, type ReactNode } from "react";
import { login as loginApi, type LoginResponse } from "@/api/auth";
import { getMe } from "@/api/auth";
import { getToken, removeToken, setToken } from "@/lib/api";
import { AuthContext } from "./auth-context-instance";
import type { User } from "./auth-context.types";

export function AuthProvider({ children }: { children: ReactNode }) {
  const token = getToken();
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(!!token);
  const [error, setError] = useState<string | null>(null);

  const handleLogout = useCallback(() => {
    removeToken();
    setUser(null);
    setError(null);
  }, []);

  // 初始化：若 localStorage 有 token，则校验有效性
  useEffect(() => {
    if (!token) return;

    let cancelled = false;
    getMe()
      .then((data) => {
        if (!cancelled) setUser(data);
      })
      .catch(() => {
        if (!cancelled) {
          removeToken();
          setUser(null);
        }
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [token]);

  const handleLogin = useCallback(async (username: string, password: string) => {
    setIsLoading(true);
    setError(null);
    try {
      const data: LoginResponse = await loginApi(username, password);
      setToken(data.access_token);
      setUser({ username: data.username });
    } catch (err) {
      const message = err instanceof Error ? err.message : "登录失败";
      setError(message);
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, []);

  const clearError = useCallback(() => setError(null), []);

  return (
    <AuthContext.Provider
      value={{
        user,
        isLoading,
        error,
        login: handleLogin,
        logout: handleLogout,
        clearError,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}
