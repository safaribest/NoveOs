import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  ChevronLeft,
  ChevronRight,
  Pencil,
  Check,
  X,
  MoreHorizontal,
  FileText,
  AlignLeft,
  Loader2,
  Play,
  Heading,
} from "lucide-react";
import { TypewriterText } from "@/components/typewriter-text";
import { LiquidProgress } from "@/components/design/liquid-progress";
import { MetricItem } from "./metrics";
import { formatNumber } from "./utils";
import { countChineseChars } from "@/lib/utils";
import type { ProjectSummary } from "./types";
import type { ChapterMeta } from "@/api/projects";

interface EditorCanvasProps {
  project: ProjectSummary | null;
  chapters: ChapterMeta[];
  selectedChapter: number | null;
  selectedMeta: ChapterMeta | undefined;
  chapterContent: string;
  editedContent: string;
  isEditing: boolean;
  isLoadingContent: boolean;
  isSavingContent: boolean;
  isStreaming: boolean;
  saveContentError: string;
  completedBanner: boolean;
  wordGoalProgress: number;
  readerPullScore: number | null;
  onPrevChapter: () => void;
  onNextChapter: () => void;
  onStartEdit: () => void;
  onCancelEdit: () => void;
  onSaveContent: () => void;
  onContentChange: (value: string) => void;
  onDismissCompleted: () => void;
  onStart: () => void;
  actionLoading: string;
}

const thinScrollbarStyle: React.CSSProperties = {
  scrollbarWidth: "thin",
  scrollbarColor: "var(--color-border) transparent",
};

export function EditorCanvas({
  project,
  chapters,
  selectedChapter,
  selectedMeta,
  chapterContent,
  editedContent,
  isEditing,
  isLoadingContent,
  isSavingContent,
  isStreaming,
  saveContentError,
  completedBanner,
  wordGoalProgress,
  readerPullScore,
  onPrevChapter,
  onNextChapter,
  onStartEdit,
  onCancelEdit,
  onSaveContent,
  onContentChange,
  onDismissCompleted,
  onStart,
  actionLoading,
}: EditorCanvasProps) {
  const wordCount = countChineseChars(chapterContent);
  const inputWordCount = isEditing ? countChineseChars(editedContent) : wordCount;
  const readTime = Math.max(1, Math.round(wordCount / 300));

  return (
    <main className="flex min-w-0 flex-1 flex-col overflow-hidden rounded-xl border border-border bg-card">
      {/* 标题行 */}
      <div className="flex items-center justify-between border-b border-border/50 px-5 py-3">
        <div className="flex min-w-0 items-center gap-3">
          <Button
            variant="ghost"
            size="icon"
            className="size-7 rounded-full text-muted-foreground hover:bg-foreground/5 hover:text-foreground"
            disabled={!selectedChapter}
            onClick={onPrevChapter}
            title="上一章 (←)"
          >
            <ChevronLeft className="size-4" />
          </Button>
          <div className="min-w-0">
            <h2 className="truncate text-sm font-semibold text-foreground">
              {selectedChapter ? `第 ${selectedChapter} 章` : "章节内容"}
              {selectedMeta?.title ? ` · ${selectedMeta.title}` : ""}
            </h2>
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <span>{formatNumber(wordCount)} 字</span>
              <span>·</span>
              <span>{isSavingContent ? "保存中" : isEditing ? "未保存" : "已保存"}</span>
            </div>
          </div>
          <Button
            variant="ghost"
            size="icon"
            className="size-7 rounded-full text-muted-foreground hover:bg-foreground/5 hover:text-foreground"
            disabled={!selectedChapter}
            onClick={onNextChapter}
            title="下一章 (→)"
          >
            <ChevronRight className="size-4" />
          </Button>
        </div>

        <div className="flex items-center gap-1">
          {selectedChapter && !isLoadingContent && (
            <>
              {isEditing ? (
                <>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={onCancelEdit}
                    disabled={isSavingContent}
                    className="rounded-full text-xs"
                  >
                    <X className="mr-1 size-3.5" />
                    取消
                  </Button>
                  <Button
                    size="sm"
                    onClick={onSaveContent}
                    disabled={isSavingContent}
                    className="rounded-full bg-primary px-3 text-xs text-primary-foreground hover:bg-primary-hover"
                  >
                    {isSavingContent ? (
                      <Loader2 className="mr-1 size-3.5 animate-spin" />
                    ) : (
                      <Check className="mr-1 size-3.5" />
                    )}
                    保存
                  </Button>
                </>
              ) : (
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={onStartEdit}
                      className="size-8 rounded-full text-muted-foreground hover:bg-foreground/5 hover:text-foreground"
                    >
                      <Pencil className="size-4" />
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>编辑章节内容</TooltipContent>
                </Tooltip>
              )}
            </>
          )}
          <Button
            variant="ghost"
            size="icon"
            className="size-8 rounded-full text-muted-foreground hover:bg-foreground/5 hover:text-foreground"
          >
            <MoreHorizontal className="size-4" />
          </Button>
        </div>
      </div>

      {/* Markdown 工具栏 */}
      {selectedChapter && (
        <div className="flex items-center gap-1 border-b border-border/50 bg-background/40 px-4 py-2">
          <Tooltip>
            <TooltipTrigger asChild>
              <Button variant="ghost" size="icon" className="size-8 rounded-lg text-muted-foreground hover:bg-foreground/5 hover:text-foreground">
                <Heading className="size-4" />
              </Button>
            </TooltipTrigger>
            <TooltipContent>标题样式</TooltipContent>
          </Tooltip>
          <div className="mx-2 h-4 w-px bg-border" />
          <span className="text-xs text-muted-foreground">Markdown 快捷工具栏</span>
        </div>
      )}

      {/* 正文区域 */}
      <div className="relative flex min-h-0 flex-1 flex-col overflow-hidden">
        <div
          className="flex-1 overflow-y-auto px-6 py-6"
          style={thinScrollbarStyle}
        >
          {isLoadingContent ? (
            <div className="space-y-3 py-4">
              {Array.from({ length: 7 }).map((_, i) => (
                <Skeleton key={i} className="h-5" style={{ width: `${[75, 100, 83, 66, 100, 80, 60][i]}%` }} />
              ))}
            </div>
          ) : selectedChapter ? (
            isEditing ? (
              <div className="space-y-3">
                <Textarea
                  value={editedContent}
                  onChange={(e) => onContentChange(e.target.value)}
                  className="min-h-[520px] resize-y rounded-xl border-border/60 bg-background leading-relaxed shadow-sm focus-visible:ring-1"
                  placeholder="在此编辑章节内容..."
                />
                {saveContentError && (
                  <div className="flex items-center gap-2 rounded-xl bg-destructive/10 px-3 py-2 text-xs text-destructive">
                    <AlignLeft className="size-4" />
                    {saveContentError}
                  </div>
                )}
              </div>
            ) : (
              <div className="max-w-none">
                <pre className="whitespace-pre-wrap font-sans text-sm leading-relaxed text-foreground">
                  {isStreaming ? (
                    <TypewriterText text={chapterContent} speed={10} />
                  ) : (
                    chapterContent
                  )}
                  {isStreaming && (
                    <span className="ml-0.5 inline-block h-4 w-0.5 animate-pulse bg-primary align-middle" />
                  )}
                </pre>
                {isStreaming && (
                  <p className="mt-3 text-xs text-muted-foreground">
                    AI 正在写作 · {formatNumber(wordCount)} 字
                    <span className="ml-2 inline-block size-1.5 rounded-full bg-emerald-500 animate-pulse" />
                  </p>
                )}
              </div>
            )
          ) : chapters.length === 0 && !project ? (
            <div className="flex h-full min-h-[400px] flex-col items-center justify-center text-sm text-muted-foreground">
              <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-foreground/5">
                <AlignLeft className="size-7 opacity-50" />
              </div>
              <p>正在加载项目...</p>
            </div>
          ) : chapters.length === 0 && project ? (
            <div className="flex h-full min-h-[500px] flex-col items-center justify-center px-8 text-center">
              <div className="mb-6 flex h-16 w-16 items-center justify-center rounded-2xl bg-primary/10 ring-1 ring-primary/20">
                <FileText className="size-8 text-primary" />
              </div>
              <h3 className="text-xl font-semibold tracking-tight">准备就绪</h3>
              <p className="mt-2 max-w-sm text-sm text-muted-foreground">
                《{project.name}》已创建完成，大纲已准备 {project.total_chapters} 章。
                AI 将按大纲逐章写作，每章约 {project.words_per_chapter} 字。
              </p>
              <div className="mt-6 grid w-full max-w-xs gap-3 rounded-2xl border border-border/60 bg-foreground/[0.02] p-4 text-left text-sm">
                <div className="flex justify-between"><span className="text-muted-foreground">总章节</span><span className="font-medium">{project.total_chapters} 章</span></div>
                <div className="flex justify-between"><span className="text-muted-foreground">预计耗时</span><span className="font-medium">约 {Math.max(1, Math.round(project.total_chapters * 0.3))} - {Math.max(2, Math.round(project.total_chapters * 0.6))} 分钟</span></div>
                <div className="flex justify-between"><span className="text-muted-foreground">当前进度</span><span className="font-medium">{project.current_chapter} / {project.total_chapters}</span></div>
              </div>
              <Button
                size="lg"
                onClick={onStart}
                className="mt-6 rounded-full bg-primary px-6 text-base text-primary-foreground hover:bg-primary-hover"
                disabled={actionLoading !== "" || !project}
              >
                {actionLoading === "start" ? (
                  <Loader2 className="mr-2 size-5 animate-spin" />
                ) : (
                  <Play className="mr-2 size-5" />
                )}
                开始 AI 写作
              </Button>
              <p className="mt-3 text-xs text-muted-foreground">
                也可以先在左侧章节列表中预览大纲结构
              </p>
            </div>
          ) : (
            <div className="flex h-full min-h-[400px] flex-col items-center justify-center text-sm text-muted-foreground">
              <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-foreground/5">
                <AlignLeft className="size-7 opacity-50" />
              </div>
              <p>选择左侧章节查看内容</p>
            </div>
          )}
        </div>

        {/* 完成横幅 */}
        {completedBanner && (
          <div className="absolute bottom-4 left-4 right-4 z-10 flex items-center gap-3 rounded-xl border border-emerald-500/20 bg-emerald-500/10 px-4 py-3 text-xs text-emerald-600">
            <Check className="size-4" />
            <span className="flex-1">全部 {project?.total_chapters} 章已生成完毕！</span>
            <button
              onClick={onDismissCompleted}
              className="rounded-full p-1 text-muted-foreground transition-colors hover:bg-foreground/5 hover:text-foreground"
            >
              <X className="size-3.5" />
            </button>
          </div>
        )}
      </div>

      {/* 底部本章统计 */}
      {selectedChapter && (
        <div className="grid grid-cols-2 gap-4 border-t border-border/50 bg-background/50 px-5 py-3 sm:grid-cols-3 md:grid-cols-5">
          <MetricItem label="本章字数" value={wordCount} suffix="字" />
          <MetricItem label="输入字数" value={inputWordCount} suffix="字" />
          <MetricItem label="AI生成字数" value={wordCount} suffix="字" />
          <MetricItem label="预计阅读" value={readTime} suffix="分钟" />
          <MetricItem label="追读力评分" value={readerPullScore} />
        </div>
      )}

      {/* 状态栏 */}
      <div className="flex items-center justify-between border-t border-border/50 bg-background/60 px-5 py-2 text-xs text-muted-foreground">
        <div className="flex items-center gap-2">
          <span className="size-1.5 rounded-full bg-emerald-500" />
          自动保存已开启
        </div>
        <div className="flex items-center gap-3">
          <span className="hidden sm:inline">字数目标 {wordGoalProgress}%</span>
          <LiquidProgress value={wordGoalProgress} size="sm" className="w-24" />
        </div>
      </div>
    </main>
  );
}
