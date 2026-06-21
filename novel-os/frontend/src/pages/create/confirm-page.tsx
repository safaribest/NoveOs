import { useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { createFromOutline } from "@/api/projects";
import type { Outline, Topic } from "@/types/insight";
import { ArrowLeft, CheckCircle, AlertCircle, Loader2, BookOpen, FileText, Users, Zap } from "lucide-react";

const DRAFT_KEY = "novel-os:outline-draft";

interface LocationState {
  topic: Topic;
  categoryId: string;
  outline: Outline;
  chaptersTarget?: number;
  wordsPerChapter?: number;
}

export function ConfirmPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const queryClient = useQueryClient();
  const locationState = (location.state as LocationState) || {};

  // 若直接刷新或从本地草稿进入，尝试恢复
  const draft = useMemo(() => {
    if (locationState.topic && locationState.outline) {
      return null;
    }
    try {
      const raw = localStorage.getItem(DRAFT_KEY);
      if (raw) {
        const parsed = JSON.parse(raw);
        if (parsed.topic && parsed.outline) {
          return parsed as LocationState;
        }
      }
    } catch {
      // ignore
    }
    return null;
  }, [locationState.outline, locationState.topic]);

  const topic = locationState.topic ?? draft?.topic;
  const outline = locationState.outline ?? draft?.outline;

  // 优先使用用户在 outline 页输入的章数/字数，其次使用大纲对象中的值
  const userChaptersTarget =
    locationState.chaptersTarget ??
    draft?.chaptersTarget ??
    outline?.chapters_target ??
    outline?.outline.length ??
    0;
  const userWordsPerChapter =
    locationState.wordsPerChapter ??
    draft?.wordsPerChapter ??
    outline?.words_per_chapter ??
    2200;

  const [isCreating, setIsCreating] = useState(false);
  const [error, setError] = useState("");
  const [created, setCreated] = useState(false);
  const [projectId, setProjectId] = useState("");

  useEffect(() => {
    if (!topic || !outline) {
      navigate("/create/outline");
    }
  }, [topic, outline, navigate]);

  const handleCreate = async () => {
    if (!topic || !outline) return;
    setIsCreating(true);
    setError("");

    try {
      const response = await createFromOutline({
        title: topic.title,
        outline,
        chapters_target: userChaptersTarget,
        words_per_chapter: userWordsPerChapter,
      });
      setProjectId(response.project_id);
      setCreated(true);
      localStorage.removeItem(DRAFT_KEY);
      await queryClient.invalidateQueries({ queryKey: ["projects"] });
    } catch (err) {
      setError(err instanceof Error ? err.message : "创建项目失败");
    } finally {
      setIsCreating(false);
    }
  };

  const handleGoWrite = () => {
    navigate(`/projects/${encodeURIComponent(projectId)}/write`);
  };

  if (!topic || !outline) return null;

  return (
    <div className="space-y-6 p-8">
      <div className="mb-6">
        <h1 className="text-2xl font-bold tracking-tight">
          确认创建项目
        </h1>
        <p className="text-sm text-muted-foreground">检查大纲信息，确认后创建项目</p>
      </div>
        {/* 项目信息 */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <BookOpen className="size-5 text-primary" />
              项目信息
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <h3 className="text-xl font-bold">{topic.title}</h3>
              <p className="text-muted-foreground">{topic.hook}</p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Badge variant="secondary">{outline.platform || "起点"}</Badge>
              <Badge variant="secondary">{outline.genre || "未分类"}</Badge>
              <Badge variant="secondary">{userChaptersTarget} 章</Badge>
              <Badge variant="secondary">约 {userWordsPerChapter} 字/章</Badge>
            </div>
          </CardContent>
        </Card>

        {/* 大纲统计 */}
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Card className="lg:col-span-2">
            <CardHeader className="pb-2">
              <CardTitle className="flex items-center gap-2 text-base">
                <div className="flex size-8 items-center justify-center rounded-lg bg-primary/10 text-primary">
                  <FileText className="size-4" />
                </div>
                章节
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold">{outline.outline.length}</div>
              <p className="text-xs text-muted-foreground">{outline.volumes.length} 卷</p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="flex items-center gap-2 text-base">
                <div className="flex size-8 items-center justify-center rounded-lg bg-primary/10 text-primary">
                  <Users className="size-4" />
                </div>
                角色
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold">{outline.characters.length}</div>
              <p className="text-xs text-muted-foreground">主要人物设定</p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="flex items-center gap-2 text-base">
                <div className="flex size-8 items-center justify-center rounded-lg bg-primary/10 text-primary">
                  <Zap className="size-4" />
                </div>
                债务/伏笔
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold">
                {outline.debts.length + (outline.foreshadowing?.length || 0)}
              </div>
              <p className="text-xs text-muted-foreground">待回收线索</p>
            </CardContent>
          </Card>
        </div>

        {/* 操作区 */}
        <Card>
          <CardHeader>
            <CardTitle>创建确认</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {!created ? (
              <>
                <p className="text-sm text-muted-foreground">
                  创建项目后将生成 book.yaml、book_data.py 和 world_state.db，并注册到写作流水线。
                </p>
                <Separator />
                <div className="flex gap-2">
                  <Button variant="outline" onClick={() => navigate("/create/outline")}>
                    <ArrowLeft className="mr-2 size-4" />
                    返回修改
                  </Button>
                  <Button onClick={handleCreate} disabled={isCreating}>
                    {isCreating ? (
                      <Loader2 className="mr-2 size-4 animate-spin" />
                    ) : (
                      <CheckCircle className="mr-2 size-4" />
                    )}
                    {isCreating ? "创建中..." : "确认创建项目"}
                  </Button>
                </div>
                {isCreating && (
                  <div className="space-y-2">
                    <Progress value={60} showValue />
                    <p className="text-xs text-muted-foreground">正在初始化项目文件和数据库...</p>
                  </div>
                )}
                {error && (
                  <div className="flex items-center gap-2 rounded-md bg-destructive/10 px-4 py-3 text-sm text-destructive">
                    <AlertCircle className="size-4" />
                    {error}
                  </div>
                )}
              </>
            ) : (
              <div className="space-y-4">
                <div className="flex items-center gap-2 text-primary">
                  <CheckCircle className="size-5" />
                  <span className="font-semibold">项目创建成功！</span>
                </div>
                <p className="text-sm text-muted-foreground">项目 ID：{projectId}</p>
                <div className="flex flex-wrap gap-2">
                  <Button onClick={handleGoWrite}>进入写作控制台</Button>
                  <Button variant="outline" onClick={() => navigate("/projects")}>返回项目列表</Button>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
    </div>
  );
}
