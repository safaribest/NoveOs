import * as React from "react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { listProjects } from "@/api/projects";
import { Search, Settings, Menu } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button, type ButtonProps } from "@/components/ui/button";
import { ThemeToggle } from "@/components/theme-toggle";
import { CommandPalette } from "@/components/command-palette";
import { NotificationBell } from "@/components/notification-center";
import { UserMenu } from "@/components/user-menu";

interface BreadcrumbItem {
  label: string;
  href?: string;
}

interface TopbarProps {
  title: string;
  description?: string;
  breadcrumbs?: BreadcrumbItem[];
  children?: React.ReactNode;
  onMenuClick?: () => void;
}

function Breadcrumbs({ items }: { items: BreadcrumbItem[] }) {
  return (
    <nav aria-label="面包屑导航" className="flex items-center">
      <ol className="flex items-center gap-2 text-sm">
        {items.map((item, index) => {
          const isLast = index === items.length - 1;
          return (
            <li key={index} className="flex items-center gap-2">
              {index > 0 && (
                <span className="text-muted-foreground/50">/</span>
              )}
              {item.href && !isLast ? (
                <Link
                  to={item.href}
                  className="text-muted-foreground transition-colors hover:text-foreground"
                >
                  {item.label}
                </Link>
              ) : (
                <span
                  className={cn(
                    "font-medium",
                    isLast ? "text-foreground" : "text-muted-foreground"
                  )}
                >
                  {item.label}
                </span>
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}

function GlobalSearchTrigger({ onClick }: { onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "relative hidden w-full max-w-[16rem] items-center gap-2 rounded-lg border border-border bg-secondary px-3 sm:max-w-xs md:flex lg:max-w-sm",
        "transition-colors hover:border-border hover:bg-secondary-hover",
        "focus-visible:border-ring/60 focus-visible:bg-secondary-hover focus-visible:ring-1 focus-visible:ring-ring/20"
      )}
    >
      <Search className="size-4 shrink-0 text-muted-foreground" />
      <span className="h-9 flex-1 text-left text-sm leading-9 text-muted-foreground">
        全局搜索
      </span>
      <kbd className="hidden shrink-0 rounded border border-border/60 bg-secondary/80 px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground sm:inline-block">
        ⌘K
      </kbd>
    </button>
  );
}

function IconButton({
  children,
  label,
  className,
  ...props
}: ButtonProps & { label: string }) {
  return (
    <Button
      variant="ghost"
      size="icon"
      className={cn(
        "h-9 w-9 text-muted-foreground transition-colors hover:text-foreground",
        className
      )}
      aria-label={label}
      {...props}
    >
      {children}
    </Button>
  );
}

export function Topbar({
  title,
  description,
  breadcrumbs,
  children,
  onMenuClick,
}: TopbarProps) {
  const [commandOpen, setCommandOpen] = useState(false);
  const { data: projects = [] } = useQuery({
    queryKey: ["projects"],
    queryFn: listProjects,
    staleTime: 60_000,
  });

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setCommandOpen((v) => !v);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  return (
    <>
      <header
        className={cn(
          "flex h-14 items-center justify-between border-b border-border/60",
          "bg-card px-4 lg:px-6"
        )}
      >
        <div className="flex min-w-0 items-center gap-2">
          {onMenuClick && (
            <IconButton
              label="打开菜单"
              onClick={onMenuClick}
              className="shrink-0 md:hidden"
            >
              <Menu className="size-4" />
            </IconButton>
          )}
          {breadcrumbs && breadcrumbs.length > 0 ? (
            <Breadcrumbs items={breadcrumbs} />
          ) : (
            <div>
              <h1 className="text-xl font-semibold tracking-tight text-foreground">
                {title}
              </h1>
              {description && (
                <p className="text-sm text-muted-foreground">{description}</p>
              )}
            </div>
          )}
        </div>

        <div className="flex items-center gap-2 pl-4">
          <GlobalSearchTrigger onClick={() => setCommandOpen(true)} />
          {children}
          <IconButton label="设置" asChild>
            <Link to="/settings/llm">
              <Settings className="size-4" />
            </Link>
          </IconButton>
          <NotificationBell />
          <ThemeToggle className="h-9 w-9" />
          <UserMenu />
        </div>
      </header>

      <CommandPalette
        open={commandOpen}
        onOpenChange={setCommandOpen}
        projects={projects.map((p) => ({ project_id: p.project_id, name: p.name }))}
      />
    </>
  );
}
