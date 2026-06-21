import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  getProject,
  getProjectDashboard,
  type ProjectStatus,
  type DashboardData,
  type Volume,
} from "@/api/projects";
import {
  BookOpen,
  Users,
  Globe,
  Sword,
  Eye,
  Backpack,
  Scale,
  ArrowLeft,
  RefreshCw,
  Sparkles,
  Hash,
  MapPin,
  Heart,
  Shield,
  Lock,
  Unlock,
  Fingerprint,
  AlertCircle,
} from "lucide-react";
import { LiquidProgress } from "@/components/design/liquid-progress";
import { FadeIn } from "@/components/design/fade-in";

type TabId = "outline" | "characters" | "world" | "skills" | "foreshadowing" | "items" | "debts";

interface TabDef {
  id: TabId;
  label: string;
  icon: React.ReactNode;
}

const TABS: TabDef[] = [
  { id: "outline", label: "大纲", icon: <BookOpen className="size-4" /> },
  { id: "characters", label: "人物", icon: <Users className="size-4" /> },
  { id: "world", label: "世界观", icon: <Globe className="size-4" /> },
  { id: "skills", label: "技能", icon: <Sword className="size-4" /> },
  { id: "foreshadowing", label: "伏笔", icon: <Eye className="size-4" /> },
  { id: "items", label: "道具", icon: <Backpack className="size-4" /> },
  { id: "debts", label: "债务", icon: <Scale className="size-4" /> },
];

function tryParseList(value: string | undefined | null): string[] {
  if (!value) return [];
  try {
    const parsed = JSON.parse(value);
    if (Array.isArray(parsed)) return parsed.map((item) => String(item));
  } catch {
    // fall through
  }
  return value.split(",").map((s) => s.trim()).filter(Boolean);
}

function StatusBadge({ status }: { status?: string }) {
  const variant =
    status === "collected"
      ? "success"
      : status === "abandoned"
        ? "secondary"
        : "default";
  return <Badge variant={variant}>{status || "active"}</Badge>;
}

function EmptyState({ message }: { message: string }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-border bg-muted/20 py-16 text-center">
      <Sparkles className="mb-3 size-8 text-muted-foreground/60" />
      <p className="text-sm text-muted-foreground">{message}</p>
    </div>
  );
}

function SectionTitle({ icon, title, count }: { icon: React.ReactNode; title: string; count?: number }) {
  return (
    <div className="flex items-center gap-2 text-base font-semibold tracking-tight">
      <span className="text-primary">{icon}</span>
      {title}
      {count !== undefined && <Badge variant="secondary">{count}</Badge>}
    </div>
  );
}

function OutlineTab({ outline }: { outline: DashboardData["outline"] }) {
  const volumes = outline.volumes || [];
  const chapters = outline.chapters || [];

  return (
    <div className="space-y-6">
      {volumes.length > 0 && (
        <section className="space-y-3">
          <SectionTitle icon={<BookOpen className="size-4" />} title="分卷结构" count={volumes.length} />
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {volumes.map((volume: Volume, idx) => (
              <Card key={`${volume.title || idx}-${idx}`}>
                <CardHeader className="pb-3">
                  <div className="flex items-center justify-between gap-2">
                    <Badge variant="outline">卷 {volume.index || idx + 1}</Badge>
                    {volume.range && <span className="text-xs text-muted-foreground">{volume.range}</span>}
                  </div>
                  <CardTitle className="text-base">{volume.title || "未命名卷"}</CardTitle>
                  {volume.theme && <CardDescription>{volume.theme}</CardDescription>}
                </CardHeader>
                {volume.climax && (
                  <CardContent className="pt-0">
                    <p className="text-xs leading-relaxed text-muted-foreground">
                      <span className="font-medium text-foreground">高潮：</span>
                      {volume.climax}
                    </p>
                  </CardContent>
                )}
              </Card>
            ))}
          </div>
        </section>
      )}

      <section className="space-y-3">
        <SectionTitle icon={<Hash className="size-4" />} title="章节规划" count={chapters.length} />
        {chapters.length === 0 ? (
          <EmptyState message="暂无大纲章节" />
        ) : (
          <div className="space-y-3">
            {chapters.map((ch) => (
              <div
                key={ch.chapter}
                className="rounded-lg border border-border bg-card p-4 transition-colors hover:border-primary/20"
              >
                  <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                    <div className="flex items-start gap-3 md:w-2/3">
                      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-primary/10 text-xs font-semibold text-primary">
                        {ch.chapter}
                      </div>
                      <div className="min-w-0 space-y-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="font-medium">{ch.title || `第 ${ch.chapter} 章`}</span>
                          {ch.arc && <Badge variant="secondary">{ch.arc}</Badge>}
                        </div>
                        {ch.core_event && (
                          <p className="text-sm leading-relaxed text-muted-foreground">
                            {ch.core_event}
                          </p>
                        )}
                        {ch.chapter_hook && (
                          <p className="text-xs italic leading-relaxed text-foreground/70">
                            钩子：{ch.chapter_hook}
                          </p>
                        )}
                      </div>
                    </div>
                    <div className="flex flex-wrap gap-2 md:flex-col md:items-end md:justify-start">
                      {ch.skill_unlocked && (
                        <Badge variant="default" className="gap-1">
                          <Sparkles className="size-3" />
                          {ch.skill_unlocked}
                        </Badge>
                      )}
                      {ch.emotion_ratio && (
                        <span className="text-xs text-muted-foreground">情绪 {ch.emotion_ratio}</span>
                      )}
                    </div>
                  </div>
                </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

function CharactersTab({ characters }: { characters: DashboardData["characters"] }) {
  if (characters.length === 0) return <EmptyState message="暂无人物设定" />;
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {characters.map((c) => (
        <Card key={`${c.name}-${c.chapter}`}>
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between gap-2">
              <CardTitle className="text-base">{c.name}</CardTitle>
              <Badge variant="outline">第 {c.chapter} 章</Badge>
            </div>
            {c.physical_description && (
              <CardDescription className="line-clamp-2">{c.physical_description}</CardDescription>
            )}
          </CardHeader>
          <CardContent className="space-y-2 pt-0 text-sm">
            {c.location && (
              <div className="flex items-start gap-2 text-muted-foreground">
                <MapPin className="mt-0.5 size-3.5 shrink-0" />
                <span>{c.location}</span>
              </div>
            )}
            {c.emotional_state && (
              <div className="flex items-start gap-2 text-muted-foreground">
                <Heart className="mt-0.5 size-3.5 shrink-0" />
                <span>{c.emotional_state}</span>
              </div>
            )}
            {c.abilities_active && (
              <div className="flex items-start gap-2 text-muted-foreground">
                <Shield className="mt-0.5 size-3.5 shrink-0" />
                <span className="line-clamp-2">{c.abilities_active}</span>
              </div>
            )}
            {c.dialog_fingerprint && (
              <div className="flex items-start gap-2 text-muted-foreground">
                <Fingerprint className="mt-0.5 size-3.5 shrink-0" />
                <span className="line-clamp-2">{c.dialog_fingerprint}</span>
              </div>
            )}
            {(c.known_secrets || c.unknown_secrets) && (
              <div className="space-y-1 pt-1">
                {c.known_secrets && (
                  <div className="flex items-start gap-1.5 text-xs text-success">
                    <Unlock className="mt-0.5 size-3 shrink-0" />
                    <span className="line-clamp-3">{c.known_secrets}</span>
                  </div>
                )}
                {c.unknown_secrets && (
                  <div className="flex items-start gap-1.5 text-xs text-warning">
                    <Lock className="mt-0.5 size-3 shrink-0" />
                    <span className="line-clamp-3">{c.unknown_secrets}</span>
                  </div>
                )}
              </div>
            )}
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

function WorldTab({ outline, terms }: { outline: DashboardData["outline"]; terms: DashboardData["terms"] }) {
  return (
    <div className="space-y-6">
      <section className="space-y-3">
        <SectionTitle icon={<BookOpen className="size-4" />} title="世界观概要" />
        {outline.summary ? (
          <Card>
            <CardContent className="p-4">
              <p className="leading-relaxed text-foreground/90">{outline.summary}</p>
            </CardContent>
          </Card>
        ) : (
          <EmptyState message="暂无世界观概要" />
        )}
      </section>

      <section className="space-y-3">
        <SectionTitle icon={<Globe className="size-4" />} title="术语词典" count={terms.length} />
        {terms.length === 0 ? (
          <EmptyState message="暂无术语设定" />
        ) : (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {terms.map((term) => (
              <Card key={term.term}>
                <CardHeader className="pb-2">
                  <div className="flex items-center justify-between gap-2">
                    <CardTitle className="text-base">{term.term}</CardTitle>
                    {term.category && <Badge variant="secondary">{term.category}</Badge>}
                  </div>
                </CardHeader>
                <CardContent className="space-y-1 pt-0">
                  {term.description && (
                    <p className="text-sm text-muted-foreground">{term.description}</p>
                  )}
                  {term.first_chapter !== undefined && term.first_chapter !== null && (
                    <p className="text-xs text-muted-foreground">首次出现：第 {term.first_chapter} 章</p>
                  )}
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

function SkillsTab({ skills }: { skills: DashboardData["skills"] }) {
  if (skills.length === 0) return <EmptyState message="暂无技能设定" />;
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {skills.map((skill) => {
        const used = tryParseList(skill.used_chapters);
        return (
          <Card key={skill.skill_name}>
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between gap-2">
                <CardTitle className="text-base">{skill.skill_name}</CardTitle>
                {skill.unlock_chapter !== undefined && skill.unlock_chapter !== null && (
                  <Badge variant="default">第 {skill.unlock_chapter} 章解锁</Badge>
                )}
              </div>
            </CardHeader>
            <CardContent className="space-y-2 pt-0">
              {skill.description && (
                <p className="text-sm text-muted-foreground">{skill.description}</p>
              )}
              {used.length > 0 && (
                <div className="flex flex-wrap gap-1 pt-1">
                  {used.map((chapter) => (
                    <Badge key={chapter} variant="outline" className="text-[10px]">
                      第 {chapter} 章使用
                    </Badge>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}

function ForeshadowingTab({ items }: { items: DashboardData["foreshadowing"] }) {
  if (items.length === 0) return <EmptyState message="暂无伏笔设定" />;
  return (
    <div className="space-y-3">
      {items.map((item) => (
        <div
          key={item.fs_id}
          className="rounded-lg border border-border bg-card p-4 transition-colors hover:border-primary/20"
        >
            <div className="flex flex-col gap-2 md:flex-row md:items-start md:justify-between">
              <div className="space-y-1 md:w-3/4">
                <p className="text-sm leading-relaxed">{item.content}</p>
                {item.type && <p className="text-xs text-muted-foreground">类型：{item.type}</p>}
              </div>
              <div className="flex flex-wrap gap-2 md:flex-col md:items-end">
                <StatusBadge status={item.status} />
                <div className="flex gap-2 text-xs text-muted-foreground">
                  <span>埋：{item.bury_chapter}</span>
                  {item.collect_chapter && <span>收：{item.collect_chapter}</span>}
                </div>
              </div>
            </div>
          </div>
      ))}
    </div>
  );
}

function ItemsTab({ items }: { items: DashboardData["items"] }) {
  if (items.length === 0) return <EmptyState message="暂无道具设定" />;
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {items.map((item) => {
        const rules = tryParseList(item.rule);
        return (
          <Card key={`${item.item_name}-${item.chapter}`}>
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between gap-2">
                <CardTitle className="text-base">{item.item_name}</CardTitle>
                <Badge variant="outline">第 {item.chapter} 章</Badge>
              </div>
            </CardHeader>
            <CardContent className="space-y-2 pt-0 text-sm">
              {item.location && (
                <div className="flex items-start gap-2 text-muted-foreground">
                  <MapPin className="mt-0.5 size-3.5 shrink-0" />
                  <span>{item.location}</span>
                </div>
              )}
              {item.state && (
                <div className="flex items-start gap-2 text-muted-foreground">
                  <Shield className="mt-0.5 size-3.5 shrink-0" />
                  <span>状态：{item.state}</span>
                </div>
              )}
              {rules.length > 0 && (
                <div className="space-y-1 pt-1">
                  {rules.map((rule, idx) => (
                    <p key={idx} className="text-xs text-muted-foreground">• {rule}</p>
                  ))}
                </div>
              )}
              {item.state_history && (
                <p className="line-clamp-2 text-xs text-muted-foreground/70">{item.state_history}</p>
              )}
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}

function DebtsTab({ debts }: { debts: DashboardData["debts"] }) {
  if (debts.length === 0) return <EmptyState message="暂无债务设定" />;
  return (
    <div className="space-y-3">
      {debts.map((debt) => (
        <div
          key={debt.debt_id}
          className="rounded-lg border border-border bg-card p-4 transition-colors hover:border-primary/20"
        >
            <div className="flex flex-col gap-2 md:flex-row md:items-start md:justify-between">
              <div className="space-y-1 md:w-3/4">
                <p className="text-sm leading-relaxed">{debt.content}</p>
                {debt.type && <p className="text-xs text-muted-foreground">类型：{debt.type}</p>}
              </div>
              <div className="flex flex-wrap gap-2 md:flex-col md:items-end">
                <StatusBadge status={debt.status} />
                <div className="flex gap-2 text-xs text-muted-foreground">
                  <span>埋：{debt.bury_chapter}</span>
                  {debt.collect_chapter !== undefined && debt.collect_chapter !== null && (
                    <span>收：{debt.collect_chapter}</span>
                  )}
                </div>
              </div>
            </div>
          </div>
      ))}
    </div>
  );
}

export function DashboardPage() {
  const { id: projectId } = useParams<{ id: string }>();
  const [project, setProject] = useState<ProjectStatus | null>(null);
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [activeTab, setActiveTab] = useState<TabId>("outline");

  const fetchAll = useCallback(async () => {
    if (!projectId) return;
    setLoading(true);
    setError("");
    try {
      const [projectRes, dashboardRes] = await Promise.all([
        getProject(projectId),
        getProjectDashboard(projectId),
      ]);
      setProject(projectRes);
      setData(dashboardRes);
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载看板失败");
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    fetchAll();
  }, [fetchAll]);

  const progress = useMemo(() => {
    if (!project || project.total_chapters <= 0) return 0;
    const current = project.completed_chapters ?? project.current_chapter ?? 0;
    return Math.min(100, Math.round((current / project.total_chapters) * 100));
  }, [project]);

  const renderTab = () => {
    if (!data) return null;
    switch (activeTab) {
      case "outline":
        return <OutlineTab outline={data.outline} />;
      case "characters":
        return <CharactersTab characters={data.characters} />;
      case "world":
        return <WorldTab outline={data.outline} terms={data.terms} />;
      case "skills":
        return <SkillsTab skills={data.skills} />;
      case "foreshadowing":
        return <ForeshadowingTab items={data.foreshadowing} />;
      case "items":
        return <ItemsTab items={data.items} />;
      case "debts":
        return <DebtsTab debts={data.debts} />;
      default:
        return null;
    }
  };

  if (!projectId) {
    return (
      <div className="p-8">
        <div className="text-destructive">缺少项目 ID</div>
      </div>
    );
  }

  return (
    <FadeIn className="min-h-screen bg-background">
      <main className="space-y-6 p-4 md:p-6 lg:p-8">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="text-2xl font-bold tracking-tight">
              项目看板
            </h1>
            <p className="text-sm text-muted-foreground">
              {project ? `《${project.name}》设定总览` : "加载中..."}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" asChild>
              <Link to={`/projects/${encodeURIComponent(projectId)}/write`}>
                <ArrowLeft className="mr-1 size-4" />
                写作控制台
              </Link>
            </Button>
            <Button variant="ghost" size="icon" onClick={fetchAll} disabled={loading}>
              <RefreshCw className={`size-4 ${loading ? "animate-spin" : ""}`} />
            </Button>
          </div>
        </div>

        {/* 项目概览 */}
        <Card>
          <CardContent className="p-4 md:p-6">
            {loading && !project ? (
              <div className="space-y-3">
                <Skeleton className="h-6 w-1/3" />
                <Skeleton className="h-4 w-1/2" />
                <Skeleton className="h-2 w-full" />
              </div>
            ) : project ? (
              <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
                <div className="space-y-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <h2 className="text-2xl font-semibold tracking-tight">《{project.name}》</h2>
                    <Badge variant="secondary">{project.genre}</Badge>
                    <Badge variant="outline">{project.platform}</Badge>
                  </div>
                  <p className="text-sm text-muted-foreground">
                    总章节 {project.total_chapters} 章 · 已完成{" "}
                    {project.completed_chapters ?? project.current_chapter} 章 · 当前状态{" "}
                    <span className="font-medium text-foreground">{project.status}</span>
                  </p>
                </div>
                <div className="w-full md:w-1/3">
                  <LiquidProgress value={progress} size="md" showLabel />
                </div>
              </div>
            ) : (
              <div className="flex items-center gap-2 text-destructive">
                <AlertCircle className="size-4" />
                {error || "加载失败"}
              </div>
            )}
          </CardContent>
        </Card>

        {error && (
          <div className="flex items-center gap-2 rounded-md bg-destructive/10 px-4 py-3 text-sm text-destructive">
            <AlertCircle className="size-4" />
            {error}
          </div>
        )}

        {/* Tab 导航 */}
        <div className="sticky top-0 z-10 -mx-4 px-4 md:-mx-6 md:px-6 lg:-mx-8 lg:px-8">
          <div className="overflow-x-auto pb-2">
            <div className="flex min-w-max gap-2 rounded-xl border border-border/60 bg-card/80 p-1.5 backdrop-blur-xl">
              {TABS.map((tab) => {
                const active = activeTab === tab.id;
                return (
                  <button
                    key={tab.id}
                    onClick={() => setActiveTab(tab.id)}
                    className={`
                      flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm font-medium transition-all
                      ${active ? "bg-primary text-primary-foreground shadow-sm" : "text-muted-foreground hover:bg-secondary hover:text-foreground"}
                    `}
                  >
                    {tab.icon}
                    {tab.label}
                  </button>
                );
              })}
            </div>
          </div>
        </div>

        {/* Tab 内容 */}
        <div className="min-h-[400px]">
          {loading && !data ? (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {Array.from({ length: 6 }).map((_, i) => (
                <Skeleton key={i} className="h-40 w-full rounded-xl" />
              ))}
            </div>
          ) : data ? (
            renderTab()
          ) : null}
        </div>
      </main>
    </FadeIn>
  );
}
