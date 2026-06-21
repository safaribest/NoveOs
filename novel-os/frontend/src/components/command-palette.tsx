import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Dialog,
  DialogContent,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import {
  Search,
  FolderKanban,
  PenLine,
  Settings,
  FileText,
  Home,
} from "lucide-react";

interface CommandPaletteProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  projects: { project_id: string; name: string }[];
}

interface CommandItem {
  id: string;
  label: string;
  description?: string;
  icon: React.ReactNode;
  href?: string;
  onSelect?: () => void;
}

export function CommandPalette({ open, onOpenChange, projects }: CommandPaletteProps) {
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const [activeIndex, setActiveIndex] = useState(0);
  const listRef = useRef<HTMLDivElement>(null);
  const itemRefs = useRef<(HTMLButtonElement | null)[]>([]);

  const commands: CommandItem[] = useMemo(() => {
    const q = query.trim().toLowerCase();
    const staticItems: CommandItem[] = [
      {
        id: "nav-home",
        label: "仪表盘",
        description: "返回项目总览",
        icon: <Home className="size-4" />,
        href: "/",
      },
      {
        id: "nav-projects",
        label: "项目列表",
        description: "查看所有项目",
        icon: <FolderKanban className="size-4" />,
        href: "/projects",
      },
      {
        id: "nav-create",
        label: "创建项目",
        description: "新建一个网文项目",
        icon: <PenLine className="size-4" />,
        href: "/create/category",
      },
      {
        id: "nav-settings",
        label: "LLM 配置",
        description: "管理模型与 Agent",
        icon: <Settings className="size-4" />,
        href: "/settings/llm",
      },
    ];

    const projectItems: CommandItem[] = projects.map((p) => ({
      id: `project-${p.project_id}`,
      label: p.name,
      description: "打开项目",
      icon: <FileText className="size-4" />,
      href: `/projects/${encodeURIComponent(p.project_id)}/write`,
    }));

    const all = [...staticItems, ...projectItems];
    if (!q) return all;

    return all.filter((item) => {
      const text = `${item.label} ${item.description || ""}`.toLowerCase();
      return text.includes(q);
    });
  }, [projects, query]);

  const safeIndex = commands.length === 0 ? 0 : Math.min(activeIndex, commands.length - 1);

  useEffect(() => {
    const selected = itemRefs.current[safeIndex];
    if (selected) {
      selected.scrollIntoView({ block: "nearest" });
    }
  }, [safeIndex]);

  const handleOpenChange = (nextOpen: boolean) => {
    onOpenChange(nextOpen);
    if (!nextOpen) {
      setQuery("");
      setActiveIndex(0);
    }
  };

  const handleQueryChange = (value: string) => {
    setQuery(value);
    setActiveIndex(0);
  };

  const handleSelect = (item: CommandItem) => {
    handleOpenChange(false);
    if (item.onSelect) {
      item.onSelect();
    } else if (item.href) {
      navigate(item.href);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (commands.length === 0) return;

    switch (e.key) {
      case "ArrowDown":
        e.preventDefault();
        setActiveIndex((i) => (i + 1) % commands.length);
        break;
      case "ArrowUp":
        e.preventDefault();
        setActiveIndex((i) => (i - 1 + commands.length) % commands.length);
        break;
      case "Enter":
        e.preventDefault();
        handleSelect(commands[safeIndex]);
        break;
      case "Escape":
        e.preventDefault();
        handleOpenChange(false);
        break;
    }
  };

  const selectedId = commands[safeIndex]?.id;

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent
        className="gap-0 overflow-hidden border-border bg-popover p-0 shadow-2xl sm:max-w-lg"
        onKeyDown={handleKeyDown}
      >
        <DialogTitle className="sr-only">命令面板</DialogTitle>
        <div className="flex items-center gap-3 border-b border-border px-4 py-3">
          <Search className="size-4 text-muted-foreground" />
          <Input
            value={query}
            onChange={(e) => handleQueryChange(e.target.value)}
            placeholder="搜索页面、项目或操作..."
            className="h-8 border-0 bg-transparent px-0 text-sm shadow-none focus-visible:ring-0"
            autoFocus
            aria-autocomplete="list"
            aria-controls="command-listbox"
            aria-activedescendant={selectedId}
          />
          <kbd className="hidden rounded border border-border bg-secondary px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground sm:inline-block">
            ESC
          </kbd>
        </div>
        <div
          ref={listRef}
          id="command-listbox"
          role="listbox"
          className="max-h-[60vh] overflow-y-auto p-2"
        >
          {commands.length === 0 ? (
            <div className="py-8 text-center text-sm text-muted-foreground">
              未找到匹配项
            </div>
          ) : (
            <div className="space-y-1">
              {commands.map((item, index) => {
                const isActive = index === safeIndex;
                return (
                  <button
                    key={item.id}
                    ref={(el) => { itemRefs.current[index] = el; }}
                    type="button"
                    role="option"
                    id={item.id}
                    aria-selected={isActive}
                    onClick={() => handleSelect(item)}
                    onMouseEnter={() => setActiveIndex(index)}
                    className={cn(
                      "flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left transition-colors",
                      isActive
                        ? "bg-primary/10 text-primary"
                        : "hover:bg-muted"
                    )}
                  >
                    <span className="flex size-8 shrink-0 items-center justify-center rounded-md bg-secondary text-muted-foreground">
                      {item.icon}
                    </span>
                    <div className="min-w-0 flex-1">
                      <div className="text-sm font-medium">{item.label}</div>
                      {item.description && (
                        <div className="text-xs text-muted-foreground">{item.description}</div>
                      )}
                    </div>
                  </button>
                );
              })}
            </div>
          )}
        </div>
        <div className="flex items-center justify-between border-t border-border bg-muted/30 px-4 py-2 text-[10px] text-muted-foreground">
          <span>↑↓ 选择 · ↵ 确认 · ESC 关闭</span>
          <span>{commands.length} 个结果</span>
        </div>
      </DialogContent>
    </Dialog>
  );
}
