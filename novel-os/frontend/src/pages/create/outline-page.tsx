import { useEffect, useMemo, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { generateOutline, getTask } from "@/api/insights";
import type { Outline, OutlineItem, Topic } from "@/types/insight";
import { Sparkles, ArrowLeft, AlertCircle, CheckCircle, BookOpen, Zap, Shield } from "lucide-react";

interface LocationState {
  topic: Topic;
  categoryId: string;
}

const DRAFT_KEY = "novel-os:outline-draft";

interface DraftState {
  topic: Topic;
  categoryId: string;
  outline: Outline | null;
  editedOutline: OutlineItem[];
  platform: string;
  style: string;
  chaptersTarget: number;
  wordsPerChapter: number;
  extraNotes: string;
  savedAt: string;
}

const PLATFORM_OPTIONS = [
  { value: "起点", label: "起点" },
  { value: "番茄", label: "番茄" },
  { value: "七猫", label: "七猫" },
  { value: "晋江", label: "晋江" },
];

export function OutlinePage() {
  const navigate = useNavigate();
  const location = useLocation();
  const locationState = (location.state as LocationState) || {};

  // 优先用路由 state，没有则尝试从 localStorage 恢复草稿
  const initialDraft = useMemo<DraftState | null>(() => {
    if (locationState.topic && locationState.categoryId) {
      return null;
    }
    try {
      const raw = localStorage.getItem(DRAFT_KEY);
      if (raw) {
        const parsed = JSON.parse(raw) as DraftState;
        if (parsed.topic && parsed.categoryId) {
          return parsed;
        }
      }
    } catch {
      // ignore parse error
    }
    return null;
  }, [locationState.categoryId, locationState.topic]);

  const topic = locationState.topic ?? initialDraft?.topic;
  const categoryId = locationState.categoryId ?? initialDraft?.categoryId;

  const [platform, setPlatform] = useState(initialDraft?.platform ?? "起点");
  const [style, setStyle] = useState(initialDraft?.style ?? "快节奏爽文");
  const [chaptersTarget, setChaptersTarget] = useState(initialDraft?.chaptersTarget ?? 50);
  const [wordsPerChapter, setWordsPerChapter] = useState(initialDraft?.wordsPerChapter ?? 2200);
  const [extraNotes, setExtraNotes] = useState(initialDraft?.extraNotes ?? "");

  const [taskId, setTaskId] = useState("");
  const [outline, setOutline] = useState<Outline | null>(initialDraft?.outline ?? null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [error, setError] = useState("");
  const [taskProgress, setTaskProgress] = useState(0);
  const [editedOutline, setEditedOutline] = useState<OutlineItem[]>(initialDraft?.editedOutline ?? []);
  const [resultTab, setResultTab] = useState("structure");
  const pollingRef = useRef(false);

  // 当关键状态变化时持久化到 localStorage，防止误操作刷新/离开丢失
  useEffect(() => {
    if (!topic || !categoryId) return;
    const draft: DraftState = {
      topic,
      categoryId,
      outline,
      editedOutline,
      platform,
      style,
      chaptersTarget,
      wordsPerChapter,
      extraNotes,
      savedAt: new Date().toISOString(),
    };
    try {
      localStorage.setItem(DRAFT_KEY, JSON.stringify(draft));
    } catch {
      // ignore quota error
    }
  }, [categoryId, chaptersTarget, editedOutline, extraNotes, outline, platform, style, topic, wordsPerChapter]);

  useEffect(() => {
    if (!topic || !categoryId) {
      navigate("/create/topics");
    }
  }, [topic, categoryId, navigate]);

  const handleGenerate = async () => {
    if (!topic || !categoryId) return;
    if (chaptersTarget < 3 || chaptersTarget > 2000) {
      setError("目标章数需在 3~2000 之间");
      return;
    }
    if (wordsPerChapter < 500 || wordsPerChapter > 10000) {
      setError("每章字数需在 500~10000 之间");
      return;
    }
    setIsGenerating(true);
    setError("");
    setOutline(null);
    setEditedOutline([]);
    setTaskProgress(0);

    try {
      const response = await generateOutline({
        topic,
        category_id: categoryId,
        platform,
        style,
        chapters_target: chaptersTarget,
        words_per_chapter: wordsPerChapter,
        extra_notes: extraNotes,
      });
      setTaskId(response.task_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "创建大纲任务失败");
      setIsGenerating(false);
    }
  };

  useEffect(() => {
    if (!taskId) return;

    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | null = null;

    const poll = async () => {
      if (cancelled || pollingRef.current) return;
      pollingRef.current = true;
      try {
        const task = await getTask(taskId);
        if (cancelled) return;
        if (task.status === "success") {
          const result = task.result as Outline | null;
          setOutline(result);
          setEditedOutline(result?.outline || []);
          setIsGenerating(false);
          setTaskProgress(100);
          return;
        }
        if (task.status === "failed") {
          setError(task.error || "大纲生成失败");
          setIsGenerating(false);
          return;
        }
        setTaskProgress(task.progress || 0);
        timer = setTimeout(() => { pollingRef.current = false; poll(); }, 2000);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "查询任务失败");
          setIsGenerating(false);
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
  }, [taskId]);

  const updateChapterField = (index: number, field: keyof OutlineItem, value: string) => {
    setEditedOutline((prev) => {
      const next = [...prev];
      next[index] = { ...next[index], [field]: value };
      return next;
    });
  };

  const handleConfirm = () => {
    if (!outline || !topic) return;
    const finalOutline: Outline = { ...outline, outline: editedOutline };
    // 跳转到确认页时保留草稿，确认页创建成功后再清理
    navigate("/create/confirm", {
      state: {
        topic,
        categoryId,
        outline: finalOutline,
        chaptersTarget,
        wordsPerChapter,
      },
    });
  };

  if (!topic) return null;

  return (
    <div className="space-y-6 p-8">
      <div className="mb-6">
        <h1 className="text-2xl font-bold">大纲生成</h1>
        <p className="text-sm text-muted-foreground">基于选题《{topic.title}》生成完整大纲</p>
      </div>
        {/* 选题信息 */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <BookOpen className="size-5 text-primary" />
              选题信息
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <h3 className="text-lg font-semibold">{topic.title}</h3>
              <p className="text-muted-foreground">{topic.hook}</p>
            </div>
            <div className="flex flex-wrap gap-2">
              {topic.slap_points.map((point, i) => (
                <Badge key={i} variant="secondary">
                  {point}
                </Badge>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* 参数表单 */}
        {!outline && (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Sparkles className="size-5 text-primary" />
                生成参数
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-2">
                  <Label>目标平台</Label>
                  <Select
                    value={platform}
                    onValueChange={(value) => setPlatform(value)}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="选择平台" />
                    </SelectTrigger>
                    <SelectContent>
                      {PLATFORM_OPTIONS.map((option) => (
                        <SelectItem key={option.value} value={option.value}>
                          {option.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label>风格偏好</Label>
                  <Input
                    value={style}
                    onChange={(e) => setStyle(e.target.value)}
                    placeholder="如：快节奏爽文、悬疑压抑、甜宠轻松"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="chapters-target">目标章数</Label>
                  <Input
                    id="chapters-target"
                    name="chapters_target"
                    data-testid="chapters-target-input"
                    type="number"
                    min={3}
                    max={2000}
                    value={chaptersTarget}
                    onChange={(e) => {
                      const v = e.target.value;
                      setChaptersTarget(v === "" ? 0 : Number(v));
                    }}
                  />
                </div>
                <div className="space-y-2">
                  <Label>每章字数</Label>
                  <Input
                    type="number"
                    min={500}
                    max={10000}
                    value={wordsPerChapter}
                    onChange={(e) => {
                      const v = e.target.value;
                      setWordsPerChapter(v === "" ? 0 : Number(v));
                    }}
                  />
                </div>
              </div>
              <div className="space-y-2">
                <Label>额外要求</Label>
                <Textarea
                  placeholder="如：主角性格腹黑、开局必须高能、避免后宫"
                  value={extraNotes}
                  onChange={(e) => setExtraNotes(e.target.value)}
                />
              </div>
              <div className="flex gap-2">
                <Button variant="outline" onClick={() => navigate(`/create/topics?category=${categoryId}`)}>
                  <ArrowLeft className="mr-2 size-4" />
                  返回选题
                </Button>
                <Button onClick={handleGenerate} disabled={isGenerating}>
                  <Sparkles className="mr-2 size-4" />
                  {isGenerating ? "生成中..." : "生成大纲"}
                </Button>
              </div>
              {isGenerating && (
                <div className="space-y-2">
                  <Progress value={taskProgress || 45} showValue />
                  <p className="text-xs text-muted-foreground">
                    {chaptersTarget <= 10
                      ? `AI 正在生成完整大纲，约需 10~20 秒`
                      : chaptersTarget <= 50
                        ? `AI 正在生成完整大纲，${chaptersTarget} 章约 30~60 秒`
                        : `AI 正在生成完整大纲，${chaptersTarget} 章建议分多次生成`}
                  </p>
                </div>
              )}
              {error && (
                <div className="flex items-center gap-2 rounded-md bg-destructive/10 px-4 py-3 text-sm text-destructive">
                  <AlertCircle className="size-4" />
                  {error}
                </div>
              )}
            </CardContent>
          </Card>
        )}

        {/* 大纲结果 */}
        {outline && (
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle className="flex items-center gap-2">
                  <CheckCircle className="size-5 text-primary" />
                  大纲结果
                </CardTitle>
                <Button onClick={handleConfirm}>确认创建项目</Button>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Tab 切换 */}
              <div className="flex gap-1 rounded-lg bg-muted/50 p-1">
                {[
                  { key: "structure", label: "整体结构" },
                  { key: "characters", label: "角色设定" },
                  { key: "chapters", label: `章节大纲 (${editedOutline.length})` },
                  { key: "debts", label: "债务伏笔" },
                  { key: "skills", label: "规则技能" },
                ].map((tab) => (
                  <button
                    key={tab.key}
                    onClick={() => setResultTab(tab.key)}
                    className={`flex-1 rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
                      resultTab === tab.key
                        ? "bg-background text-foreground shadow-sm"
                        : "text-muted-foreground hover:text-foreground"
                    }`}
                  >
                    {tab.label}
                  </button>
                ))}
              </div>

              {resultTab === "structure" && (
                <div className="space-y-4">
                  <p className="text-sm leading-relaxed text-muted-foreground">{outline.summary}</p>
                  <Separator />
                  <div className="grid gap-4 md:grid-cols-2">
                    {(outline.volumes || []).map((vol) => (
                      <div key={vol.index} className="rounded-lg border border-border/50 bg-muted/30 p-4">
                        <div className="font-semibold">第 {vol.index} 卷 · {vol.title}</div>
                        <div className="text-xs text-muted-foreground">{vol.range}</div>
                        <div className="mt-2 text-sm">{vol.theme}</div>
                        <div className="mt-1 text-xs text-primary">高潮：{vol.climax}</div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {resultTab === "characters" && (
                <div className="grid gap-4 md:grid-cols-2">
                  {(outline.characters || []).map((c) => (
                    <div key={c.name} className="space-y-2 rounded-lg border border-border/50 bg-muted/30 p-4">
                      <div className="flex items-center justify-between">
                        <span className="font-semibold">{c.name}</span>
                        <Badge variant="outline">{c.role}</Badge>
                      </div>
                      <p className="text-sm text-muted-foreground">{c.brief}</p>
                      <p className="text-xs">弧光：{c.arc}</p>
                      <div className="flex flex-wrap gap-1">
                        {(c.tags || []).map((tag, i) => (
                          <Badge key={i} variant="secondary" className="text-xs">{tag}</Badge>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {resultTab === "chapters" && (
                <div className="max-h-[60vh] space-y-3 overflow-y-auto pr-1">
                  {editedOutline.map((ch, index) => (
                    <div key={ch.chapter} className="animate-stagger rounded-lg border p-4" style={{ animationDelay: `${index * 50}ms` }}>
                      <div className="mb-2 flex items-center gap-2">
                        <Badge>第 {ch.chapter} 章</Badge>
                        <span className="text-xs text-muted-foreground">{ch.arc}</span>
                      </div>
                      <div className="grid gap-3 md:grid-cols-2">
                        <div className="space-y-1">
                          <Label className="text-xs">标题</Label>
                          <Input value={ch.title} onChange={(e) => updateChapterField(index, "title", e.target.value)} />
                        </div>
                        <div className="space-y-1">
                          <Label className="text-xs">核心事件</Label>
                          <Input value={ch.core_event} onChange={(e) => updateChapterField(index, "core_event", e.target.value)} />
                        </div>
                        <div className="space-y-1">
                          <Label className="text-xs">打脸目标</Label>
                          <Input value={ch.face_slap_target || ""} onChange={(e) => updateChapterField(index, "face_slap_target", e.target.value)} />
                        </div>
                        <div className="space-y-1">
                          <Label className="text-xs">打脸方式</Label>
                          <Input value={ch.face_slap_method || ""} onChange={(e) => updateChapterField(index, "face_slap_method", e.target.value)} />
                        </div>
                      </div>
                      <div className="mt-2 flex flex-wrap gap-2 text-xs text-muted-foreground">
                        <span>钩子：{ch.chapter_hook || "无"}</span>
                        <span>情绪：{ch.emotion_ratio || "5:3:2"}</span>
                        {ch.skill_unlocked && <span>技能：{ch.skill_unlocked}</span>}
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {resultTab === "debts" && (
                <div className="grid gap-6 md:grid-cols-2">
                  <div>
                    <h4 className="mb-3 flex items-center gap-2 text-sm font-semibold"><Zap className="size-4 text-primary" />债务</h4>
                    <div className="space-y-2">
                      {(outline.debts || []).map((d) => (
                        <div key={d.debt_id} className="rounded-md border p-3 text-sm">
                          <div className="font-medium">{d.debt_id} · {d.type}</div>
                          <p className="text-muted-foreground">{d.content}</p>
                          <div className="mt-1 text-xs">埋于 {d.bury_chapter} 章 · 收于 {d.collect_chapter || "?"} 章</div>
                        </div>
                      ))}
                    </div>
                  </div>
                  <div>
                    <h4 className="mb-3 flex items-center gap-2 text-sm font-semibold"><Shield className="size-4 text-primary" />伏笔</h4>
                    <div className="space-y-2">
                      {(outline.foreshadowing || []).map((f) => (
                        <div key={f.debt_id} className="rounded-md border p-3 text-sm">
                          <div className="font-medium">{f.debt_id} · {f.type}</div>
                          <p className="text-muted-foreground">{f.content}</p>
                          <div className="mt-1 text-xs">埋于 {f.bury_chapter} 章 · 收于 {f.collect_chapter || "?"} 章</div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              )}

              {resultTab === "skills" && (
                <div className="grid gap-6 md:grid-cols-2">
                  <div>
                    <h4 className="mb-3 text-sm font-semibold">世界观 / 系统规则</h4>
                    <ul className="list-inside list-disc space-y-1 text-sm text-muted-foreground">
                      {(outline.rules || []).map((rule, i) => (
                        <li key={`${rule}-${i}`}>{rule}</li>
                      ))}
                    </ul>
                  </div>
                  <div>
                    <h4 className="mb-3 text-sm font-semibold">技能 / 金手指</h4>
                    <div className="space-y-2">
                      {(outline.skills || []).map((sk) => (
                        <div key={sk.name} className="rounded-md border p-3 text-sm">
                          <div className="font-medium">{sk.name} <Badge variant="outline">{sk.chapter} 章解锁</Badge></div>
                          <p className="text-muted-foreground">{sk.description}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        )}
    </div>
  );
}
