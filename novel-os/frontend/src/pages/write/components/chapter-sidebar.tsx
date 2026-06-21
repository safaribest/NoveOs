import { forwardRef } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  ChevronDown,
  Plus,
  Search,
  Filter,
  LayoutList,
  LayoutGrid,
  CheckCircle,
  Loader2,
} from "lucide-react";
import { cn } from "@/lib/utils";
import type { ChapterMeta } from "@/api/projects";
import type { ChapterAgentInfo } from "./types";
import { groupChaptersByVolume } from "./utils";

const thinScrollbarStyle: React.CSSProperties = {
  scrollbarWidth: "thin",
  scrollbarColor: "var(--color-border) transparent",
};

interface ChapterSidebarProps {
  chapters: ChapterMeta[];
  totalChapters: number;
  selectedChapter: number | null;
  currentChapter: number | null;
  chapterAgents: Map<number, ChapterAgentInfo>;
  pipelineIsRunning: boolean;
  searchQuery: string;
  viewMode: "list" | "compact";
  statusFilter: "all" | "done" | "writing" | "pending";
  onSearchChange: (value: string) => void;
  onViewModeChange: (mode: "list" | "compact") => void;
  onStatusFilterChange: (filter: "all" | "done" | "writing" | "pending") => void;
  onSelectChapter: (num: number) => void;
}

const statusFilterLabel: Record<string, string> = {
  all: "全部",
  done: "已完成",
  writing: "生成中",
  pending: "待生成",
};

export const ChapterSidebar = forwardRef<HTMLDivElement, ChapterSidebarProps>(
  function ChapterSidebar(
    {
      chapters,
      totalChapters,
      selectedChapter,
      currentChapter,
      chapterAgents,
      pipelineIsRunning,
      searchQuery,
      viewMode,
      statusFilter,
      onSearchChange,
      onViewModeChange,
      onStatusFilterChange,
      onSelectChapter,
    },
    ref
  ) {
    const isCurrentChapter = (num: number) => pipelineIsRunning && currentChapter === num;
    const chapterStatus = (ch: ChapterMeta) => {
      if (ch.word_count !== null && ch.word_count > 0) return "done";
      if (isCurrentChapter(ch.chapter_num)) return "writing";
      return "pending";
    };

    const filteredChapters = chapters.filter((ch) => {
      if (statusFilter !== "all") {
        const st = chapterStatus(ch);
        if (statusFilter !== st) return false;
      }
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const title = (ch.title || "").toLowerCase();
        if (!title.includes(q) && !String(ch.chapter_num).includes(q)) return false;
      }
      return true;
    });

    const volumeGroups = groupChaptersByVolume(filteredChapters, totalChapters || chapters.length);

    const cycleStatusFilter = () => {
      const order: ("all" | "done" | "writing" | "pending")[] = ["all", "done", "writing", "pending"];
      const idx = order.indexOf(statusFilter);
      onStatusFilterChange(order[(idx + 1) % order.length]);
    };

    const AGENT_DISPLAY_MAP: Record<string, { label: string }> = {
      director: { label: "规划师 Planner" },
      beat_planner: { label: "情节师 Plotter" },
      scene_writer: { label: "文笔师 Stylist" },
      hook_engineer: { label: "追读力评估师" },
      dialogue_tuner: { label: "对话调优师" },
      polish: { label: "润色师" },
      auditor: { label: "质检员 Reviewer" },
      expander: { label: "扩写师" },
      BatchWriter: { label: "构建" },
    };

    return (
      <aside className="flex w-[280px] shrink-0 flex-col overflow-hidden rounded-xl border border-border bg-card max-md:w-full">
        {/* 工具栏 */}
        <div className="flex flex-col gap-2 border-b border-border/50 p-3">
          <div className="flex items-center gap-2">
            <button className="inline-flex h-8 shrink-0 items-center gap-1 rounded-lg border border-border bg-background/60 px-2.5 text-xs font-medium text-foreground hover:bg-background">
              全部卷
              <ChevronDown className="size-3 text-muted-foreground" />
            </button>
            <div className="flex-1" />
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => onViewModeChange(viewMode === "list" ? "compact" : "list")}
                  className="size-8 rounded-lg text-muted-foreground hover:bg-foreground/5 hover:text-foreground"
                >
                  {viewMode === "list" ? <LayoutList className="size-4" /> : <LayoutGrid className="size-4" />}
                </Button>
              </TooltipTrigger>
              <TooltipContent>切换视图</TooltipContent>
            </Tooltip>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={cycleStatusFilter}
                  className="h-8 gap-1 rounded-lg px-2 text-xs text-muted-foreground hover:bg-foreground/5 hover:text-foreground"
                >
                  <Filter className="size-3.5" />
                  {statusFilterLabel[statusFilter]}
                </Button>
              </TooltipTrigger>
              <TooltipContent>筛选章节</TooltipContent>
            </Tooltip>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  className="size-8 rounded-lg text-muted-foreground hover:bg-foreground/5 hover:text-foreground"
                >
                  <Plus className="size-4" />
                </Button>
              </TooltipTrigger>
              <TooltipContent>新建章节</TooltipContent>
            </Tooltip>
          </div>
          <div className="relative">
            <Search className="absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={searchQuery}
              onChange={(e) => onSearchChange(e.target.value)}
              placeholder="搜索章节..."
              className="h-8 rounded-lg border-border bg-background/60 pl-8 text-xs"
            />
          </div>
        </div>

        {/* 章节列表 */}
        <div
          ref={ref}
          className="flex-1 overflow-y-auto px-2 pb-2"
          style={thinScrollbarStyle}
        >
          {volumeGroups.length === 0 && (
            <p className="px-2 py-4 text-xs text-muted-foreground">暂无章节</p>
          )}
          <div className="space-y-4 py-2">
            {volumeGroups.map((group) => (
              <div key={group.title}>
                <div className="mb-2 flex items-center justify-between px-2">
                  <span className="text-xs font-medium text-muted-foreground">
                    {group.title}
                  </span>
                  <span className="text-[10px] text-muted-foreground">
                    {group.chapters.length} 章
                  </span>
                </div>
                {viewMode === "compact" ? (
                  <div className="grid grid-cols-4 gap-1">
                    {group.chapters.map((ch) => {
                      const isSelected = selectedChapter === ch.chapter_num;
                      const isActive = isCurrentChapter(ch.chapter_num);
                      const status = chapterStatus(ch);
                      return (
                        <button
                          key={ch.chapter_num}
                          data-chapter={ch.chapter_num}
                          onClick={() => onSelectChapter(ch.chapter_num)}
                          className={cn(
                            "flex flex-col items-center justify-center gap-1 rounded-lg py-2 text-xs font-medium transition-all",
                            isSelected
                              ? "bg-primary/10 text-primary ring-1 ring-primary/20"
                              : "text-muted-foreground hover:bg-foreground/5 hover:text-foreground",
                            isActive && "bg-emerald-500/8 text-emerald-600"
                          )}
                        >
                          <span className="flex size-3 items-center justify-center">
                            {status === "done" && <CheckCircle className="size-3 text-emerald-500" />}
                            {status === "writing" && <Loader2 className="size-3 animate-spin text-primary" />}
                            {status === "pending" && <span className="block size-1.5 rounded-full border border-muted-foreground/30" />}
                          </span>
                          {ch.chapter_num}
                        </button>
                      );
                    })}
                  </div>
                ) : (
                  <div className="space-y-1">
                    {group.chapters.map((ch) => {
                      const status = chapterStatus(ch);
                      const isActive = isCurrentChapter(ch.chapter_num);
                      const isSelected = selectedChapter === ch.chapter_num;
                      const agentInfo = chapterAgents.get(ch.chapter_num);

                      return (
                        <button
                          key={ch.chapter_num}
                          data-chapter={ch.chapter_num}
                          onClick={() => onSelectChapter(ch.chapter_num)}
                          className={cn(
                            "group flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left transition-all",
                            isSelected
                              ? "bg-primary/10 text-foreground ring-1 ring-primary/20"
                              : "text-foreground hover:bg-foreground/5",
                            isActive && "bg-emerald-500/8"
                          )}
                        >
                          <span className="flex size-5 shrink-0 items-center justify-center">
                            {status === "done" && <CheckCircle className="size-3.5 text-emerald-500" />}
                            {status === "writing" && <Loader2 className="size-3.5 animate-spin text-primary" />}
                            {status === "pending" && <span className="block size-2 rounded-full border border-muted-foreground/30" />}
                          </span>
                          <div className="min-w-0 flex-1">
                            <div className="truncate text-xs font-medium">
                              第 {ch.chapter_num} 章
                              {ch.title ? ` · ${ch.title}` : ""}
                            </div>
                            <div className="text-[10px] text-muted-foreground">
                              {agentInfo && isActive ? (
                                <span className="text-primary">
                                  {AGENT_DISPLAY_MAP[agentInfo.agent]?.label || agentInfo.agent}
                                </span>
                              ) : ch.word_count != null && ch.word_count > 0 ? (
                                `${ch.word_count} 字`
                              ) : status === "writing" ? (
                                "生成中"
                              ) : (
                                "待生成"
                              )}
                            </div>
                          </div>
                        </button>
                      );
                    })}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* 底部新建章节 */}
        <div className="border-t border-border/50 p-3">
          <Button
            variant="outline"
            className="w-full gap-1.5 rounded-xl border-dashed text-xs"
          >
            <Plus className="size-3.5" />
            新建章节
          </Button>
        </div>
      </aside>
    );
  }
);
