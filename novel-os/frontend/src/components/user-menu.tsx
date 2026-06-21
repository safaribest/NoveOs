import { useState, useRef, useEffect } from "react";
import { User, LogOut, Settings, HelpCircle } from "lucide-react";
import { useAuth } from "@/hooks/use-auth";
import { Link } from "react-router-dom";
import { cn } from "@/lib/utils";

export function UserMenu() {
  const { logout, user } = useAuth();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const handleLogout = () => {
    if (confirm("确定要退出登录吗？")) {
      logout();
    }
  };

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className={cn(
          "flex h-9 w-9 items-center justify-center rounded-full",
          "border border-border/60 bg-glass/80 text-muted-foreground backdrop-blur-glass",
          "transition-colors hover:text-foreground",
          open && "border-primary/40 text-primary ring-1 ring-primary/20"
        )}
        aria-label="用户菜单"
        title="用户菜单"
      >
        <User className="size-4" />
      </button>

      {open && (
        <div className="absolute right-0 top-full z-50 mt-2 w-48 rounded-xl border border-glass-border bg-glass-bg p-1 shadow-2xl backdrop-blur-glass animate-fade-in">
          <div className="border-b border-border/60 px-3 py-2">
            <p className="text-sm font-medium">{user?.username || "用户"}</p>
            <p className="text-xs text-muted-foreground">{user?.username || "admin"}</p>
          </div>
          <div className="py-1">
            <Link
              to="/settings/llm"
              onClick={() => setOpen(false)}
              className="flex items-center gap-2 rounded-lg px-3 py-2 text-sm text-foreground transition-colors hover:bg-primary/10 hover:text-primary"
            >
              <Settings className="size-4" />
              设置
            </Link>
            <button
              type="button"
              className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm text-foreground transition-colors hover:bg-primary/10 hover:text-primary"
            >
              <HelpCircle className="size-4" />
              帮助
            </button>
          </div>
          <div className="border-t border-border/60 py-1">
            <button
              type="button"
              onClick={handleLogout}
              className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm text-destructive transition-colors hover:bg-destructive/10"
            >
              <LogOut className="size-4" />
              退出登录
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
