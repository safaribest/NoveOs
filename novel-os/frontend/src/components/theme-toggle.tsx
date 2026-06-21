import { Moon, Sun } from "lucide-react";
import { useTheme } from "@/components/theme-provider";
import { cn } from "@/lib/utils";

interface ThemeToggleProps {
  className?: string;
}

export function ThemeToggle({ className }: ThemeToggleProps) {
  const { resolvedTheme, toggleTheme } = useTheme();
  const isDark = resolvedTheme === "dark";

  return (
    <button
      type="button"
      onClick={toggleTheme}
      aria-label={isDark ? "切换到浅色模式" : "切换到暗色模式"}
      className={cn(
        "relative inline-flex h-9 w-9 items-center justify-center rounded-full",
        "bg-glass/80 backdrop-blur-glass border border-glass-border shadow-glass",
        "text-foreground transition-all duration-300 ease-out",
        "hover:bg-glass hover:scale-105 hover:shadow-md active:scale-95",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background",
        className
      )}
    >
      <Sun
        className={cn(
          "absolute size-[18px] transition-all duration-300 ease-out",
          isDark
            ? "rotate-90 scale-0 opacity-0"
            : "rotate-0 scale-100 opacity-100"
        )}
        aria-hidden="true"
      />
      <Moon
        className={cn(
          "absolute size-[18px] transition-all duration-300 ease-out",
          isDark
            ? "rotate-0 scale-100 opacity-100"
            : "-rotate-90 scale-0 opacity-0"
        )}
        aria-hidden="true"
      />
    </button>
  );
}
