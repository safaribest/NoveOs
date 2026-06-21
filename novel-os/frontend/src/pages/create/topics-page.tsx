import { useEffect, useRef, useState } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { TopicCard } from "@/components/create/topic-card";
import { TopicSkeleton } from "@/components/create/topic-skeleton";
import { getCategories, generateTopics, getTask } from "@/api/insights";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import type { Category, Topic } from "@/types/insight";
import { RefreshCw, ArrowLeft, Sparkles, AlertCircle } from "lucide-react";

function findCategoryById(categories: Category[], id: string): Category | null {
  for (const c of categories) {
    if (c.id === id) return c;
    if (c.children) {
      const found = findCategoryById(c.children, id);
      if (found) return found;
    }
  }
  return null;
}

const TOPICS_DRAFT_KEY = "novel-os:topics-draft";

function getCategoryPathNames(categories: Category[], id: string): string[] {
  const path: string[] = [];

  function dfs(nodes: Category[], current: string[]): boolean {
    for (const node of nodes) {
      const newPath = [...current, node.name];
      if (node.id === id) {
        path.push(...newPath);
        return true;
      }
      if (node.children && dfs(node.children, newPath)) {
        return true;
      }
    }
    return false;
  }

  dfs(categories, []);
  return path;
}

export function TopicsPage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  // 将 URL 中的分类参数消费到组件状态中，避免旧任务参数残留在 URL 中导致反复触发。
  const [categoryId] = useState<string>(() => {
    const fromUrl = searchParams.get("category") || "";
    if (fromUrl) return fromUrl;
    // URL 没有 category 时，尝试从 localStorage 恢复
    try {
      const raw = localStorage.getItem(TOPICS_DRAFT_KEY);
      if (raw) {
        const d = JSON.parse(raw);
        if (d.categoryId && d.topics?.length > 0) return d.categoryId;
      }
    } catch { /* ignore */ }
    return "";
  });
  const [taskId, setTaskId] = useState<string>(() => {
    try {
      const raw = localStorage.getItem(TOPICS_DRAFT_KEY);
      if (raw) {
        const d = JSON.parse(raw);
        if (d.categoryId === (searchParams.get("category") || "") && d.taskId) return d.taskId;
      }
    } catch { /* ignore */ }
    return "";
  });
  const [topics, setTopics] = useState<Topic[]>(() => {
    try {
      const raw = localStorage.getItem(TOPICS_DRAFT_KEY);
      if (raw) {
        const d = JSON.parse(raw);
        if (d.categoryId === (searchParams.get("category") || "") && d.topics?.length > 0) return d.topics;
      }
    } catch { /* ignore */ }
    return [];
  });
  const [isGenerating, setIsGenerating] = useState(false);
  const [error, setError] = useState<string>("");
  const [taskProgress, setTaskProgress] = useState(taskId ? 100 : 0);
  const generatingRef = useRef(false);
  const pollingRef = useRef(false);

  const { data: categories = [], isLoading: categoriesLoading } = useQuery({
    queryKey: ["categories"],
    queryFn: getCategories,
  });

  const category = categoryId ? findCategoryById(categories, categoryId) : null;
  const pathNames = categoryId ? getCategoryPathNames(categories, categoryId) : [];

  const startGeneration = async () => {
    if (!categoryId || generatingRef.current) return;
    generatingRef.current = true;
    setIsGenerating(true);
    setError("");
    setTopics([]);
    setTaskProgress(0);

    try {
      const response = await generateTopics({
        category_id: categoryId,
        platform: "起点",
        style: "快节奏爽文",
        chapters_target: 200,
        words_per_chapter: 2200,
      });
      setTaskId(response.task_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "创建任务失败");
      setIsGenerating(false);
      generatingRef.current = false;
      setSearchParams(new URLSearchParams(), { replace: true });
    }
  };

  useEffect(() => {
    if (!categoryId) {
      navigate("/create/category");
      return;
    }
    // 如果 localStorage 里已有该分类的选题，不再重新生成，直接恢复
    if (topics.length > 0) {
      setSearchParams(new URLSearchParams(), { replace: true });
      return;
    }
    // 延迟到下一个事件循环，避免在 effect 中同步调用 setState
    const timer = setTimeout(() => startGeneration(), 0);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [categoryId]);

  useEffect(() => {
    if (!taskId) return;
    // 如果已有 topics（从 localStorage 恢复），不再轮询
    if (topics.length > 0) return;

    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | null = null;

    const clearUrlParams = () => {
      setSearchParams(new URLSearchParams(), { replace: true });
    };

    const poll = async () => {
      if (cancelled || pollingRef.current) return;
      pollingRef.current = true;
      try {
        const task = await getTask(taskId);
        if (cancelled) return;
        if (task.status === "success") {
          setTopics(task.result || []);
          // ★ 持久化：刷新页面后恢复
          try {
            localStorage.setItem(TOPICS_DRAFT_KEY, JSON.stringify({
              categoryId,
              taskId,
              topics: task.result || [],
              savedAt: new Date().toISOString(),
            }));
          } catch { /* ignore */ }
          setIsGenerating(false);
          generatingRef.current = false;
          setTaskProgress(100);
          return;
        }
        if (task.status === "failed") {
          setError(task.error || "生成失败");
          setIsGenerating(false);
          generatingRef.current = false;
          clearUrlParams();
          return;
        }
        // 未完成，继续轮询
        setTaskProgress(task.progress || 0);
        timer = setTimeout(() => { pollingRef.current = false; poll(); }, 1500);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "查询任务失败");
          setIsGenerating(false);
          generatingRef.current = false;
          clearUrlParams();
        }
      } finally {
        pollingRef.current = false;
      }
    };

    poll();

    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [taskId, setSearchParams]);

  const handleRefresh = () => {
    startGeneration();
  };

  const handleSelectTopic = (topic: Topic) => {
    navigate("/create/outline", {
      state: { topic, categoryId },
    });
  };

  return (
    <div className="p-8">
      <div className="mb-6">
        <h1 className="text-2xl font-bold">AI 选题推荐</h1>
        <p className="text-sm text-muted-foreground">
          {categoriesLoading
            ? "加载分类中..."
            : category
              ? pathNames.join(" / ")
              : "选择感兴趣的选题"}
        </p>
      </div>
        {/* 状态栏 */}
        <Card className="mb-6">
          <CardHeader>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary/10">
                  <Sparkles className="size-5 text-primary" />
                </div>
                <div>
                  <CardTitle>
                    {isGenerating ? "正在生成选题..." : topics.length > 0 ? "已生成选题" : "准备生成"}
                  </CardTitle>
                  <p className="text-sm text-muted-foreground">
                    {category ? `分类：${category.name}` : "未选择分类"}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Button variant="outline" size="sm" onClick={() => navigate("/create/category")}>
                  <ArrowLeft className="mr-2 size-4" />
                  重选分类
                </Button>
                <Button variant="outline" size="sm" onClick={handleRefresh} disabled={isGenerating}>
                  <RefreshCw className={`mr-2 size-4 ${isGenerating ? "animate-spin" : ""}`} />
                  重新生成
                </Button>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            {isGenerating && (
              <div className="space-y-2">
                <Progress value={taskProgress || 45} showValue />
                <p className="text-xs text-muted-foreground">
                  AI 正在分析当前分类的爆款趋势，预计需要 5-15 秒
                </p>
              </div>
            )}
            {error && (
              <div className="flex items-center gap-2 rounded-md bg-destructive/10 px-4 py-3 text-sm text-destructive">
                <AlertCircle className="size-4" />
                {error}
              </div>
            )}
            {!isGenerating && !error && topics.length > 0 && (
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Badge variant="success">{topics.length} 个选题</Badge>
                点击卡片底部的「选这个」进入下一步
              </div>
            )}
          </CardContent>
        </Card>

        {/* 选题网格 */}
        {isGenerating && topics.length === 0 ? (
          <div className="grid gap-4 md:grid-cols-2">
            {[1, 2, 3, 4].map((i) => (
              <TopicSkeleton key={i} />
            ))}
          </div>
        ) : (
          <div className="grid gap-4 md:grid-cols-2">
            {topics.map((topic, i) => (
              <div key={topic.id} className="animate-stagger" style={{ animationDelay: `${i * 80}ms` }}>
                <TopicCard topic={topic} onSelect={() => handleSelectTopic(topic)} isRecommended={i === 0} />
              </div>
            ))}
          </div>
        )}
    </div>
  );
}
