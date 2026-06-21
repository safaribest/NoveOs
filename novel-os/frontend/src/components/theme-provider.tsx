import {
  createContext,
  useContext,
  useEffect,
  useLayoutEffect,
  useMemo,
  useState,
  useCallback,
  type ReactNode,
} from "react";

export type Theme = "light" | "dark" | "system";
export type ResolvedTheme = "light" | "dark";

interface ThemeProviderState {
  /** 当前主题偏好（light / dark / system） */
  theme: Theme;
  /** 实际解析后的主题（light / dark） */
  resolvedTheme: ResolvedTheme;
  /** 设置主题偏好 */
  setTheme: (theme: Theme) => void;
  /** 在 light / dark 之间切换 */
  toggleTheme: () => void;
}

const ThemeProviderContext = createContext<ThemeProviderState | undefined>(
  undefined
);

const STORAGE_KEY = "novel-os-theme";

function getSystemTheme(): ResolvedTheme {
  if (typeof window === "undefined") return "light";
  const media = window.matchMedia?.("(prefers-color-scheme: dark)");
  return media?.matches ? "dark" : "light";
}

interface ThemeProviderProps {
  children: ReactNode;
  defaultTheme?: Theme;
  storageKey?: string;
}

export function ThemeProvider({
  children,
  defaultTheme = "system",
  storageKey = STORAGE_KEY,
}: ThemeProviderProps) {
  const [theme, setThemeState] = useState<Theme>(() => {
    if (typeof window === "undefined") return defaultTheme;
    try {
      const stored = window.localStorage.getItem(storageKey) as Theme | null;
      if (stored && ["light", "dark", "system"].includes(stored)) {
        return stored;
      }
    } catch {
      // localStorage 可能不可用，忽略
    }
    return defaultTheme;
  });

  const [systemTheme, setSystemTheme] = useState<ResolvedTheme>(getSystemTheme);

  const resolvedTheme = useMemo<ResolvedTheme>(
    () => (theme === "system" ? systemTheme : theme),
    [theme, systemTheme]
  );

  // 在绘制前同步切换 html 上的 dark class，避免闪烁
  useLayoutEffect(() => {
    const root = window.document.documentElement;
    root.classList.remove("light", "dark");
    root.classList.add(resolvedTheme);
  }, [resolvedTheme]);

  // 监听系统主题变化
  useEffect(() => {
    if (typeof window === "undefined" || typeof window.matchMedia !== "function")
      return;
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    if (!media?.addEventListener) return;
    const handler = (event: MediaQueryListEvent) => {
      setSystemTheme(event.matches ? "dark" : "light");
    };
    media.addEventListener("change", handler);
    return () => media.removeEventListener("change", handler);
  }, []);

  const setTheme = useCallback((newTheme: Theme) => {
    try {
      window.localStorage.setItem(storageKey, newTheme);
    } catch {
      // ignore
    }
    setThemeState(newTheme);
  }, [storageKey]);

  const toggleTheme = useCallback(() => {
    setTheme(resolvedTheme === "dark" ? "light" : "dark");
  }, [resolvedTheme, setTheme]);

  const value = useMemo(
    () => ({ theme, resolvedTheme, setTheme, toggleTheme }),
    [theme, resolvedTheme, setTheme, toggleTheme]
  );

  return (
    <ThemeProviderContext.Provider value={value}>
      {children}
    </ThemeProviderContext.Provider>
  );
}

// eslint-disable-next-line react-refresh/only-export-components
export function useTheme(): ThemeProviderState {
  const context = useContext(ThemeProviderContext);
  if (!context) {
    throw new Error("useTheme must be used within a ThemeProvider");
  }
  return context;
}
