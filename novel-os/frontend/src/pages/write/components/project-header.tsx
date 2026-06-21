import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  Play,
  Pause,
  Square,
  Loader2,
  RefreshCw,
  MoreHorizontal,
  BookOpen,
  CalendarDays,
  Maximize2,
  Minimize2,
  Download,
} from "lucide-react";
import { formatNumber } from "./utils";
import type { ProjectSummary } from "./types";
import type { PipelineStatus } from "@/api/pipeline";
import type { ChapterMeta } from "@/api/projects";

interface ProjectHeaderProps {
  project: ProjectSummary | null;
  pipeline: PipelineStatus | null;
  chapters: ChapterMeta[];
  actionLoading: string;
  focusMode: boolean;
  onStart: () => void;
  onPause: () => void;
  onStop: () => void;
  onRefresh: () => void;
  onToggleFocus: () => void;
  onExport: () => void;
  exportLoading: boolean;
}

const statusBadgeClasses: Record<string, string> = {
  running: "bg-emerald-500/10 text-emerald-600 border border-emerald-500/20",
  success: "bg-emerald-500/10 text-emerald-600 border border-emerald-500/20",
  warning: "bg-amber-500/10 text-amber-600 border border-amber-500/20",
  error: "bg-red-500/10 text-red-600 border border-red-500/20",
  idle: "bg-muted/30 text-muted-foreground border border-border",
};

export function ProjectHeader({
  project,
  pipeline,
  chapters,
  actionLoading,
  focusMode,
  onStart,
  onPause,
  onStop,
  onRefresh,
  onToggleFocus,
  onExport,
  exportLoading,
}: ProjectHeaderProps) {
  const isComplete = project ? chapters.length >= project.total_chapters : false;

  const runningStatusText = pipeline?.is_running
    ? "运行中"
    : isComplete || project?.status === "completed"
      ? "已完成"
      : project?.status === "paused"
        ? "已暂停"
        : project?.status === "error"
          ? "错误"
          : "待启动";

  const statusVariant = pipeline?.is_running
    ? "running"
    : isComplete || project?.status === "completed"
      ? "success"
      : project?.status === "paused"
        ? "warning"
        : project?.status === "error"
          ? "error"
          : "idle";

  return (
    <header className="flex h-16 shrink-0 items-center justify-between gap-4 border-b border-border bg-card px-6">
      <div className="flex min-w-0 items-center gap-4">
        <div className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary">
          <BookOpen className="size-5" />
        </div>
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <h1 className="truncate text-base font-semibold text-foreground">
              {project?.name || "写作控制台"}
            </h1>
            <Badge
              variant="outline"
              className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${statusBadgeClasses[statusVariant]}`}
            >
              {pipeline?.is_running && (
                <span className="mr-1.5 inline-block size-1.5 rounded-full bg-emerald-500 animate-pulse" />
              )}
              {runningStatusText}
            </Badge>
          </div>
          <p className="flex items-center gap-2 truncate text-xs text-muted-foreground">
            <span>{formatNumber(project?.total_words_target || project?.total_words || 0)} 字</span>
            <span className="text-border">·</span>
            <CalendarDays className="size-3" />
            <span>
              {project?.created_at
                ? new Date(project.created_at).toLocaleDateString("zh-CN")
                : "--"}
            </span>
            <span className="text-border">·</span>
            <span>{project ? `${project.current_chapter} / ${project.total_chapters} 章` : "加载中"}</span>
          </p>
        </div>
      </div>

      <div className="flex shrink-0 items-center gap-2">
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              onClick={onStart}
              disabled={actionLoading !== "" || pipeline?.is_running || !project || isComplete}
              className="rounded-full bg-primary px-4 text-xs font-medium text-primary-foreground hover:bg-primary-hover"
            >
              {actionLoading === "start" ? (
                <Loader2 className="mr-1.5 size-3.5 animate-spin" />
              ) : (
                <Play className="mr-1.5 size-3.5" />
              )}
              {isComplete ? "已完成" : chapters.length > 0 ? "续写" : "开始"}
            </Button>
          </TooltipTrigger>
          <TooltipContent>
            {isComplete
              ? "全部章节已写完"
              : chapters.length > 0 && project
                ? `从第 ${Math.min(project.total_chapters, (project.completed_chapters ?? 0) + 1)} 章继续写作`
                : "开始写作流水线"}
          </TooltipContent>
        </Tooltip>

        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant="outline"
              size="icon"
              onClick={onPause}
              disabled={actionLoading !== "" || !pipeline?.is_running}
              className="rounded-full"
            >
              {actionLoading === "pause" ? (
                <Loader2 className="size-3.5 animate-spin" />
              ) : (
                <Pause className="size-3.5" />
              )}
            </Button>
          </TooltipTrigger>
          <TooltipContent>暂停</TooltipContent>
        </Tooltip>

        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant="outline"
              size="icon"
              onClick={onStop}
              disabled={actionLoading !== "" || !pipeline?.is_running}
              className="rounded-full"
            >
              {actionLoading === "stop" ? (
                <Loader2 className="size-3.5 animate-spin" />
              ) : (
                <Square className="size-3.5" />
              )}
            </Button>
          </TooltipTrigger>
          <TooltipContent>停止</TooltipContent>
        </Tooltip>

        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant="ghost"
              size="icon"
              onClick={onRefresh}
              className="rounded-full text-muted-foreground hover:bg-foreground/5 hover:text-foreground"
            >
              <RefreshCw className="size-3.5" />
            </Button>
          </TooltipTrigger>
          <TooltipContent>刷新状态</TooltipContent>
        </Tooltip>

        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant="ghost"
              size="icon"
              onClick={onToggleFocus}
              className="rounded-full text-muted-foreground hover:bg-foreground/5 hover:text-foreground"
            >
              {focusMode ? <Minimize2 className="size-4" /> : <Maximize2 className="size-4" />}
            </Button>
          </TooltipTrigger>
          <TooltipContent>{focusMode ? "退出专注模式" : "进入专注模式"}</TooltipContent>
        </Tooltip>

        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant="outline"
              size="icon"
              onClick={onExport}
              disabled={exportLoading || chapters.length === 0}
              className="rounded-full"
            >
              {exportLoading ? (
                <Loader2 className="size-3.5 animate-spin" />
              ) : (
                <Download className="size-3.5" />
              )}
            </Button>
          </TooltipTrigger>
          <TooltipContent>导出全部章节</TooltipContent>
        </Tooltip>

        <Button
          variant="ghost"
          size="icon"
          className="rounded-full text-muted-foreground hover:bg-foreground/5 hover:text-foreground"
        >
          <MoreHorizontal className="size-4" />
        </Button>
      </div>
    </header>
  );
}
