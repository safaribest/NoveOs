import { useEffect, useRef, useState, useCallback, useMemo } from "react";
import { useParams } from "react-router-dom";
import { toast } from "@/lib/toast";
import { countChineseChars } from "@/lib/utils";
import {
  getProject,
  listChapters,
  getChapterContent,
  saveChapterContent,
  type ChapterMeta,
} from "@/api/projects";
import {
  getPipelineStatus,
  startPipeline,
  pausePipeline,
  stopPipeline,
  type PipelineStatus,
} from "@/api/pipeline";
import { streamLogs } from "@/api/logs";
import { getChapterQualityGate, type ChapterQualityGate } from "@/api/metrics";
import { AlertCircle } from "lucide-react";
import {
  TooltipProvider,
} from "@/components/ui/tooltip";
import { ProjectHeader } from "./components/project-header";
import { ChapterSidebar } from "./components/chapter-sidebar";
import { EditorCanvas } from "./components/editor-canvas";
import { InfoPanels } from "./components/info-panels";
import { parseLogMetadata, isWritingEvent } from "./components/utils";
import type { ProjectSummary, ChapterAgentInfo } from "./components/types";

export function WritePage() {
  const { id: projectId } = useParams<{ id: string }>();

  const [project, setProject] = useState<ProjectSummary | null>(null);
  const [pipeline, setPipeline] = useState<PipelineStatus | null>(null);
  const [chapters, setChapters] = useState<ChapterMeta[]>([]);
  const [selectedChapter, setSelectedChapter] = useState<number | null>(null);
  const [chapterContent, setChapterContent] = useState<string>("");
  const [editedContent, setEditedContent] = useState<string>("");
  const [isEditing, setIsEditing] = useState(false);
  const [isSavingContent, setIsSavingContent] = useState(false);
  const [saveContentError, setSaveContentError] = useState<string>("");
  const [isLoadingContent, setIsLoadingContent] = useState(false);
  const [error, setError] = useState<string>("");
  const [actionLoading, setActionLoading] = useState<string>("");
  const [dismissed, setDismissed] = useState(false);
  const [chapterAgents, setChapterAgents] = useState<Map<number, ChapterAgentInfo>>(new Map());
  const [activeChapter, setActiveChapter] = useState<number | null>(null);
  const [chapterQuality, setChapterQuality] = useState<ChapterQualityGate | null>(null);
  const [isLoadingQuality, setIsLoadingQuality] = useState(false);
  const [focusMode, setFocusMode] = useState(false);
  const [exportLoading, setExportLoading] = useState(false);

  const [searchQuery, setSearchQuery] = useState("");
  const [viewMode, setViewMode] = useState<"list" | "compact">("list");
  const [statusFilter, setStatusFilter] = useState<"all" | "done" | "writing" | "pending">("all");

  const pipelineRef = useRef<PipelineStatus | null>(pipeline);
  const selectedChapterRef = useRef<number | null>(selectedChapter);
  const isEditingRef = useRef<boolean>(isEditing);
  const activeChapterRef = useRef<number | null>(activeChapter);

  useEffect(() => { pipelineRef.current = pipeline; }, [pipeline]);
  useEffect(() => { selectedChapterRef.current = selectedChapter; }, [selectedChapter]);
  useEffect(() => { isEditingRef.current = isEditing; }, [isEditing]);
  useEffect(() => { activeChapterRef.current = activeChapter; }, [activeChapter]);

  const abortRef = useRef<AbortController | null>(null);
  const intervalRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const chapterListRef = useRef<HTMLDivElement | null>(null);
  const contentRefreshTsRef = useRef<number>(0);

  const fetchAll = useCallback(async () => {
    if (!projectId) return;
    try {
      const [projectRes, pipelineRes, chaptersRes] = await Promise.all([
        getProject(projectId),
        getPipelineStatus(projectId),
        listChapters(projectId),
      ]);
      setProject(projectRes as ProjectSummary);
      setPipeline(pipelineRes);
      setChapters(chaptersRes);
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载项目失败");
    }
  }, [projectId]);

  const fetchChapterContent = useCallback(async (chapterNum: number, options?: { reset?: boolean }) => {
    if (!projectId) return;

    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    if (options?.reset) {
      setIsLoadingContent(true);
      setChapterContent("");
      setEditedContent("");
    }

    try {
      const res = await getChapterContent(projectId, chapterNum);
      if (!controller.signal.aborted) {
        setChapterContent(res.content);
        if (options?.reset) {
          setEditedContent(res.content);
        }
      }
    } catch {
      if (!controller.signal.aborted) {
        if (options?.reset) {
          setChapterContent("章节内容暂不可用，可能尚未生成。");
          setEditedContent("章节内容暂不可用，可能尚未生成。");
        }
      }
    } finally {
      if (!controller.signal.aborted && options?.reset) {
        setIsLoadingContent(false);
      }
    }
  }, [projectId]);

  const fetchChapterQuality = useCallback(async (chapterNum: number) => {
    if (!projectId) return;
    setIsLoadingQuality(true);
    try {
      const data = await getChapterQualityGate(projectId, chapterNum);
      setChapterQuality(data);
    } catch {
      setChapterQuality(null);
    } finally {
      setIsLoadingQuality(false);
    }
  }, [projectId]);

  const handleStart = useCallback(async () => {
    if (!projectId || !project) return;
    setActionLoading("start");
    try {
      const total = project.total_chapters;
      const completed = project.completed_chapters ?? 0;
      const next = Math.min(total, Math.max(1, completed + 1));
      await startPipeline(projectId, `${next}-${total}`, true);
      await fetchAll();
    } catch (err) {
      setError(err instanceof Error ? err.message : "启动失败");
    } finally {
      setActionLoading("");
    }
  }, [projectId, project, fetchAll]);

  const handlePause = useCallback(async () => {
    if (!projectId) return;
    setActionLoading("pause");
    try {
      await pausePipeline(projectId);
      await fetchAll();
    } catch (err) {
      setError(err instanceof Error ? err.message : "暂停失败");
    } finally {
      setActionLoading("");
    }
  }, [projectId, fetchAll]);

  const handleStop = useCallback(async () => {
    if (!projectId) return;
    setActionLoading("stop");
    try {
      await stopPipeline(projectId);
      await fetchAll();
    } catch (err) {
      setError(err instanceof Error ? err.message : "停止失败");
    } finally {
      setActionLoading("");
    }
  }, [projectId, fetchAll]);

  const handleExport = useCallback(async () => {
    if (!projectId || chapters.length === 0) return;
    setExportLoading(true);
    try {
      const sorted = [...chapters].sort((a, b) => a.chapter_num - b.chapter_num);
      const contents: string[] = [];
      for (const ch of sorted) {
        try {
          const { content } = await getChapterContent(projectId, ch.chapter_num);
          const num = ch.chapter_num;
          const titleText = ch.title ? `第${num}章 ${ch.title}` : `第${num}章`;
          contents.push(`\n\n${titleText}\n${'='.repeat(titleText.length)}\n\n${content}`);
        } catch {
          contents.push(`\n\n第${ch.chapter_num}章\n\n[加载失败]`);
        }
      }
      const name = project?.name || projectId;
      const blob = new Blob([contents.join("\n")], { type: "text/plain;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${name}.txt`;
      a.click();
      URL.revokeObjectURL(url);
      toast.success(`已导出 ${sorted.length} 章`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "导出失败");
    } finally {
      setExportLoading(false);
    }
  }, [projectId, chapters, project]);

  const handleSelectChapter = useCallback((chapterNum: number) => {
    if (chapterNum === selectedChapter) return;
    setSelectedChapter(chapterNum);
    setIsEditing(false);
    setSaveContentError("");
    setChapterQuality(null);
    fetchChapterContent(chapterNum, { reset: true });
    fetchChapterQuality(chapterNum);
  }, [selectedChapter, fetchChapterContent, fetchChapterQuality]);

  const handleStartEdit = useCallback(() => {
    setEditedContent(chapterContent);
    setIsEditing(true);
    setSaveContentError("");
  }, [chapterContent]);

  const handleCancelEdit = useCallback(() => {
    setEditedContent(chapterContent);
    setIsEditing(false);
    setSaveContentError("");
  }, [chapterContent]);

  const handleSaveContent = useCallback(async () => {
    if (!projectId || selectedChapter == null) return;
    setIsSavingContent(true);
    setSaveContentError("");
    try {
      await toast.promise(
        (async () => {
          await saveChapterContent(projectId, selectedChapter, editedContent);
          setChapterContent(editedContent);
          setIsEditing(false);
          await fetchAll();
        })(),
        {
          loading: "正在保存章节...",
          success: "章节已保存",
          error: (err: unknown) => (err instanceof Error ? err.message : "保存失败"),
        }
      );
    } catch (err) {
      setSaveContentError(err instanceof Error ? err.message : "保存失败");
    } finally {
      setIsSavingContent(false);
    }
  }, [projectId, selectedChapter, editedContent, fetchAll]);

  const goToPrevChapter = useCallback(() => {
    if (!selectedChapter || chapters.length === 0) return;
    const sorted = [...chapters].sort((a, b) => a.chapter_num - b.chapter_num);
    const idx = sorted.findIndex((c) => c.chapter_num === selectedChapter);
    if (idx > 0) handleSelectChapter(sorted[idx - 1].chapter_num);
  }, [selectedChapter, chapters, handleSelectChapter]);

  const goToNextChapter = useCallback(() => {
    if (!selectedChapter || chapters.length === 0) return;
    const sorted = [...chapters].sort((a, b) => a.chapter_num - b.chapter_num);
    const idx = sorted.findIndex((c) => c.chapter_num === selectedChapter);
    if (idx < sorted.length - 1) handleSelectChapter(sorted[idx + 1].chapter_num);
  }, [selectedChapter, chapters, handleSelectChapter]);

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "s") {
        if (isEditing && !isSavingContent) {
          e.preventDefault();
          handleSaveContent();
        }
        return;
      }
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;
      if (e.key === "ArrowLeft") goToPrevChapter();
      if (e.key === "ArrowRight") goToNextChapter();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [goToPrevChapter, goToNextChapter, isEditing, isSavingContent, handleSaveContent]);

  useEffect(() => {
    if (!projectId) return;

    let cancelled = false;
    let logStream: { close: () => void } | null = null;

    const initialTimer = setTimeout(() => {
      fetchAll();
    }, 0);

    const runLoop = async () => {
      if (cancelled) return;
      try {
        await fetchAll();
        const ps = await getPipelineStatus(projectId);
        if (cancelled) return;
        const nextDelay = ps.is_running ? 3_000 : 30_000;
        intervalRef.current = setTimeout(runLoop, nextDelay);
      } catch {
        if (cancelled) return;
        intervalRef.current = setTimeout(runLoop, 30_000);
      }
    };
    intervalRef.current = setTimeout(runLoop, 3_000);

    logStream = streamLogs(
      projectId,
      (log) => {
        const eventType = log.agent;
        const chapterNum = log.chapter_num;

        if (eventType === "agent_call_start" && chapterNum != null) {
          const metadata = parseLogMetadata(log.metadata);
          const agentName = typeof metadata?.agent === "string" ? metadata.agent : "unknown";
          setChapterAgents((prev) => {
            const next = new Map(prev);
            next.set(chapterNum, { agent: agentName, ts: Date.now() });
            return next;
          });
        }

        if ((eventType === "chapter_start" || eventType === "agent_call_start") && chapterNum != null) {
          setActiveChapter(chapterNum);
          if (
            pipelineRef.current?.is_running &&
            !isEditingRef.current &&
            selectedChapterRef.current !== chapterNum
          ) {
            setSelectedChapter(chapterNum);
            fetchChapterContent(chapterNum, { reset: true });
          }
        }

        if (
          chapterNum != null &&
          chapterNum === selectedChapterRef.current &&
          !isEditingRef.current &&
          isWritingEvent(eventType)
        ) {
          const now = Date.now();
          if (now - contentRefreshTsRef.current > 2_000) {
            fetchChapterContent(chapterNum, { reset: false });
            contentRefreshTsRef.current = now;
          }
        }
      },
      {
        onError: (err) => {
          console.warn("日志流异常:", err.message);
        },
      }
    );

    return () => {
      cancelled = true;
      clearTimeout(initialTimer);
      if (intervalRef.current) {
        clearTimeout(intervalRef.current);
        intervalRef.current = null;
      }
      logStream?.close();
    };
  }, [projectId, fetchAll, fetchChapterContent]);

  useEffect(() => {
    if (pipeline?.is_running && project) {
      document.title = `写作中 (${project.current_chapter}/${project.total_chapters}) - ${project.name}`;
    } else if (project) {
      document.title = `${project.name} - Novel-OS`;
    }
    return () => {
      document.title = "Novel-OS";
    };
  }, [pipeline?.is_running, project]);

  useEffect(() => {
    if (pipeline?.is_running && selectedChapter === null && chapters.length > 0) {
      queueMicrotask(() => handleSelectChapter(chapters[0].chapter_num));
    }
  }, [pipeline?.is_running, chapters, selectedChapter, handleSelectChapter]);

  useEffect(() => {
    if (
      pipeline?.is_running &&
      selectedChapter != null &&
      selectedChapter === project?.current_chapter &&
      !isEditing
    ) {
      const timer = setInterval(() => {
        fetchChapterContent(selectedChapter, { reset: false });
        contentRefreshTsRef.current = Date.now();
      }, 3_000);
      return () => clearInterval(timer);
    }
  }, [pipeline?.is_running, selectedChapter, project?.current_chapter, isEditing, fetchChapterContent]);

  const prevCurrentRef = useRef(project?.current_chapter);
  useEffect(() => {
    const prev = prevCurrentRef.current;
    const curr = project?.current_chapter;
    prevCurrentRef.current = curr;
    if (
      !isEditing &&
      prev != null &&
      curr != null &&
      curr > prev &&
      selectedChapter === prev &&
      selectedChapter < (project?.total_chapters || 0)
    ) {
      queueMicrotask(() => handleSelectChapter(prev + 1));
    }
  }, [project?.current_chapter, selectedChapter, project?.total_chapters, isEditing, handleSelectChapter]);

  const isCompleted = useMemo(() => {
    if (!project || project.total_chapters <= 0) return false;
    return project.current_chapter >= project.total_chapters;
  }, [project]);

  const completedBanner = isCompleted && !dismissed;

  useEffect(() => {
    queueMicrotask(() => setDismissed(false));
  }, [projectId]);

  useEffect(() => {
    if (pipeline?.is_running && project?.current_chapter != null && chapterListRef.current) {
      const el = chapterListRef.current.querySelector(
        `[data-chapter="${project.current_chapter}"]`
      ) as HTMLElement | null;
      el?.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
  }, [pipeline?.is_running, project?.current_chapter]);

  const selectedMeta = useMemo(
    () => chapters.find((c) => c.chapter_num === selectedChapter),
    [chapters, selectedChapter]
  );

  const wordCount = countChineseChars(chapterContent);
  const inputWordCount = isEditing ? countChineseChars(editedContent) : wordCount;
  const wordGoal = project?.words_per_chapter || 0;
  const wordGoalProgress = wordGoal > 0 ? Math.min(100, Math.round((wordCount / wordGoal) * 100)) : 0;

  const currentAgentName = selectedChapter != null
    ? chapterAgents.get(selectedChapter)?.agent
    : activeChapter != null
      ? chapterAgents.get(activeChapter)?.agent
      : undefined;

  const isStreamingChapter = useCallback(
    (num: number) => pipeline?.is_running && (project?.current_chapter === num || activeChapter === num),
    [pipeline?.is_running, project?.current_chapter, activeChapter]
  );

  const isStreaming = selectedChapter != null && !!isStreamingChapter(selectedChapter);

  const qualityScore = useMemo(() => {
    if (chapterQuality?.aggregate_score != null) {
      return chapterQuality.aggregate_score;
    }
    if (
      pipeline?.reader_pull_score != null &&
      selectedChapter === project?.current_chapter
    ) {
      const raw = pipeline.reader_pull_score;
      return Math.round(raw <= 1 ? raw * 100 : raw);
    }
    return null;
  }, [
    chapterQuality?.aggregate_score,
    pipeline?.reader_pull_score,
    selectedChapter,
    project?.current_chapter,
  ]);

  const readerPullScore = useMemo(() => {
    if (chapterQuality?.reader_pull_score != null) {
      const raw = chapterQuality.reader_pull_score;
      return Math.round(raw <= 1 ? raw * 100 : raw);
    }
    return null;
  }, [chapterQuality]);

  const qualityMetrics = useMemo(() => {
    if (chapterQuality?.dimensions && chapterQuality.dimensions.length > 0) {
      return chapterQuality.dimensions;
    }
    return [
      { label: "情节完整性", value: null },
      { label: "文笔流畅度", value: null },
      { label: "人设一致性", value: null },
      { label: "爽点密度", value: null },
      { label: "合规质检", value: pipeline?.audit?.quality_passed ? 100 : null },
    ];
  }, [chapterQuality, pipeline?.audit?.quality_passed]);

  if (!projectId) {
    return (
      <div className="flex h-[100dvh] items-center justify-center bg-background p-8">
        <div className="rounded-2xl border border-destructive/20 bg-destructive/10 px-6 py-4 text-destructive">
          缺少项目 ID
        </div>
      </div>
    );
  }

  return (
    <TooltipProvider>
    <div className="flex h-full flex-col overflow-hidden bg-background">
      <ProjectHeader
        project={project}
        pipeline={pipeline}
        chapters={chapters}
        actionLoading={actionLoading}
        focusMode={focusMode}
        onStart={handleStart}
        onPause={handlePause}
        onStop={handleStop}
        onRefresh={fetchAll}
        onToggleFocus={() => setFocusMode((v) => !v)}
        onExport={handleExport}
        exportLoading={exportLoading}
      />

      <div className="flex min-h-0 flex-1 gap-4 overflow-hidden p-4 max-md:flex-col max-md:overflow-y-auto">
        {!focusMode && (
          <ChapterSidebar
            ref={chapterListRef}
            chapters={chapters}
            totalChapters={project?.total_chapters || 0}
            selectedChapter={selectedChapter}
            currentChapter={project?.current_chapter || null}
            chapterAgents={chapterAgents}
            pipelineIsRunning={pipeline?.is_running || false}
            searchQuery={searchQuery}
            viewMode={viewMode}
            statusFilter={statusFilter}
            onSearchChange={setSearchQuery}
            onViewModeChange={setViewMode}
            onStatusFilterChange={setStatusFilter}
            onSelectChapter={handleSelectChapter}
          />
        )}

        <EditorCanvas
          project={project}
          chapters={chapters}
          selectedChapter={selectedChapter}
          selectedMeta={selectedMeta}
          chapterContent={chapterContent}
          editedContent={editedContent}
          isEditing={isEditing}
          isLoadingContent={isLoadingContent}
          isSavingContent={isSavingContent}
          isStreaming={isStreaming}
          saveContentError={saveContentError}
          completedBanner={completedBanner}
          wordGoalProgress={wordGoalProgress}
          readerPullScore={readerPullScore}
          onPrevChapter={goToPrevChapter}
          onNextChapter={goToNextChapter}
          onStartEdit={handleStartEdit}
          onCancelEdit={handleCancelEdit}
          onSaveContent={handleSaveContent}
          onContentChange={setEditedContent}
          onDismissCompleted={() => setDismissed(true)}
          onStart={handleStart}
          actionLoading={actionLoading}
        />

        {!focusMode && (
          <InfoPanels
            currentAgentName={currentAgentName}
            qualityScore={qualityScore}
            qualityMetrics={qualityMetrics}
            isLoadingQuality={isLoadingQuality}
            wordCount={wordCount}
            inputWordCount={inputWordCount}
            wordGoal={wordGoal}
          />
        )}
      </div>

      {error && (
        <div className="absolute bottom-4 left-1/2 z-40 flex -translate-x-1/2 items-center gap-2 rounded-xl border border-destructive/20 bg-destructive/10 px-4 py-2.5 text-xs text-destructive">
          <AlertCircle className="size-4" />
          {error}
        </div>
      )}
    </div>
    </TooltipProvider>
  );
}
