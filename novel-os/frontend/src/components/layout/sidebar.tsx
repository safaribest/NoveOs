import { cn } from "@/lib/utils";
import {
  BookOpen,
  ChevronLeft,
  FileText,
  FolderKanban,
  Gauge,
  PenLine,
  Settings,
} from "lucide-react";
import { NavLink, useLocation, matchPath } from "react-router-dom";
import { useMemo } from "react";

interface SidebarProps {
  currentProject?: { id: string; name: string };
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
}

interface NavItem {
  label: string;
  href: string;
  icon: React.ComponentType<{ className?: string }>;
  pattern?: string;
}

function useGroups(currentProject?: { id: string; name: string }) {
  return useMemo(
    () => [
      {
        label: "仪表盘",
        items: [{ label: "仪表盘", href: "/", icon: Gauge, pattern: "/" }],
      },
      {
        label: "创作",
        items: [
          { label: "项目列表", href: "/projects", icon: FolderKanban, pattern: "/projects" },
          { label: "创建项目", href: "/create", icon: PenLine, pattern: "/create/*" },
          ...(currentProject
            ? [
                {
                  label: "写作工作台",
                  href: `/projects/${encodeURIComponent(currentProject.id)}/write`,
                  icon: FileText,
                  pattern: "/projects/:id/write",
                } as NavItem,
              ]
            : []),
        ],
      },
      {
        label: "系统",
        items: [{ label: "LLM 配置", href: "/settings/llm", icon: Settings, pattern: "/settings/llm" }],
      },
    ],
    [currentProject]
  );
}

function useIsActive(pattern?: string) {
  const { pathname } = useLocation();
  return useMemo(() => {
    if (!pattern) return false;
    if (pattern.endsWith("/*")) {
      return pathname.startsWith(pattern.slice(0, -2)) || matchPath(pattern, pathname) != null;
    }
    return matchPath(pattern, pathname) != null || pathname === pattern;
  }, [pathname, pattern]);
}

function NavLinkItem({ item }: { item: NavItem }) {
  const isActive = useIsActive(item.pattern);
  const Icon = item.icon;

  return (
    <NavLink
      to={item.href}
      className={cn(
        "group relative flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-all",
        isActive
          ? "bg-primary/10 text-primary"
          : "text-muted-foreground hover:bg-secondary/70 hover:text-foreground"
      )}
    >
      <Icon className="size-4 shrink-0 transition-colors" />
      {item.label}
    </NavLink>
  );
}

export function Sidebar({ currentProject, open, onOpenChange }: SidebarProps) {
  const groups = useGroups(currentProject);
  return (
    <aside
      className={cn(
        "fixed left-0 top-0 z-40 flex h-[100dvh] w-64 flex-col border-r border-border bg-card",
        "transition-transform duration-300 ease-in-out",
        "max-md:-translate-x-full",
        open && "max-md:translate-x-0"
      )}
    >
      {/* Logo */}
      <div className="flex h-16 shrink-0 items-center gap-3 border-b border-border px-5">
        <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary/10 text-primary shadow-sm">
          <BookOpen className="size-5" />
        </div>
        <div>
          <h1 className="text-lg font-bold tracking-tight text-foreground">
            Novel-OS
          </h1>
          <p className="text-xs text-muted-foreground">
            AI 写作系统
          </p>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 space-y-4 overflow-y-auto px-3 py-4">
        {groups.map((group) => (
          <div key={group.label}>
            <p className="mb-2 px-3 text-xs font-medium text-muted-foreground/70">
              {group.label}
            </p>
            <div className="space-y-1">
              {group.items.map((item) => (
                <NavLinkItem key={item.href} item={item} />
              ))}
            </div>
          </div>
        ))}
      </nav>

      {/* Bottom section */}
      <div className="shrink-0 space-y-3 border-t border-border p-3">
        {/* Current project selector */}
        <div className="rounded-xl border border-border bg-background/60 p-3 shadow-sm">
          <p className="mb-1 text-xs font-medium text-muted-foreground/70">
            当前项目
          </p>
          <p className="truncate text-sm font-medium text-foreground">
            {currentProject?.name ?? "未选择项目"}
          </p>
        </div>

        {/* Mobile close button */}
        <button
          type="button"
          onClick={() => onOpenChange?.(false)}
          className="flex w-full items-center justify-center gap-2 rounded-lg border border-border bg-secondary/50 px-3 py-2 text-xs font-medium text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground md:hidden"
        >
          <ChevronLeft className="size-4" />
          收起导航
        </button>
      </div>
    </aside>
  );
}
