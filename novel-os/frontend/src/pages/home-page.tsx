import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { getLLMSettings } from "@/api/settings";
import { listProjects } from "@/api/projects";
import { useQuery } from "@tanstack/react-query";
import { PlusCircle, Settings, Sparkles, BookOpen, ChevronRight, Cpu, PenTool, Layers } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";
import { LiquidProgress } from "@/components/design/liquid-progress";

function StatCard({
  icon: Icon,
  label,
  value,
  description,
  className,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: string | number;
  description: string;
  className?: string;
}) {
  return (
    <Card className={className}>
      <CardHeader className="pb-3">
        <div className="flex items-center gap-2">
          <div className="flex size-8 items-center justify-center rounded-lg bg-primary/10 text-primary">
            <Icon className="size-4" />
          </div>
          <CardDescription>{label}</CardDescription>
        </div>
        <CardTitle className="mt-2 text-3xl">{value}</CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-sm text-muted-foreground">{description}</p>
      </CardContent>
    </Card>
  );
}

export function HomePage() {
  const navigate = useNavigate();
  const { data: llmSettings } = useQuery({
    queryKey: ["llm-settings"],
    queryFn: getLLMSettings,
  });
  const { data: projects = [], isLoading: projectsLoading, error: projectsError } = useQuery({
    queryKey: ["projects"],
    queryFn: listProjects,
    staleTime: 0,
    refetchOnMount: "always",
  });

  const defaultProvider = llmSettings?.default_provider;
  const totalChapters = projects.reduce((sum, p) => sum + (p.completed_chapters ?? p.current_chapter), 0);
  const sortedByDate = [...projects].sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
  const activeProjects = sortedByDate.filter((p) => p.status === "writing");
  const recentProjects = sortedByDate.slice(0, 3);

  const statValue = (value: string | number, fallback: string) => {
    if (projectsLoading) return "…";
    if (projectsError) return "-";
    return value ?? fallback;
  };

  return (
    <div className="space-y-8 p-8">
      {/* Hero */}
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">
            项目总览
          </h1>
          <p className="mt-1 text-muted-foreground">管理和创作你的网文项目</p>
        </div>
        <div className="flex flex-wrap gap-3">
          <Button asChild>
            <Link to="/create/category">
              <PlusCircle className="size-4" />
              新建项目
            </Link>
          </Button>
          <Button variant="outline" asChild>
            <Link to="/settings/llm">
              <Settings className="size-4" />
              配置 LLM
            </Link>
          </Button>
        </div>
      </div>

      {/* Bento Grid Stats */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          icon={Layers}
          label="项目总数"
          value={statValue(projects.length, "0")}
          description={projects.length === 0 ? "开始创建你的第一个故事" : `${projects.length} 个进行中或已完成的项目`}
        />
        <StatCard
          icon={BookOpen}
          label="已完成章节"
          value={statValue(totalChapters, "0")}
          description="累计创作章节数"
        />
        <StatCard
          icon={PenTool}
          label="今日字数"
          value="—"
          description="今日创作字数统计"
        />
        <StatCard
          icon={Cpu}
          label="默认 LLM"
          value={defaultProvider || "未配置"}
          description={defaultProvider ? `当前默认 Provider：${defaultProvider}` : "配置后才能使用洞察和写作功能"}
        />
      </div>

      {/* Active projects */}
      {activeProjects.length > 0 && (
        <section className="space-y-4">
          <div className="flex items-center gap-2">
            <span className="relative flex size-2">
              <span className="absolute inline-flex size-full animate-ping rounded-full bg-success opacity-75" />
              <span className="relative inline-flex size-2 rounded-full bg-success" />
            </span>
            <h2 className="text-lg font-semibold">进行中的项目</h2>
          </div>
          <div className="grid gap-4 md:grid-cols-2">
            {activeProjects.map((project) => {
              const completed = project.completed_chapters ?? project.current_chapter;
              const pct = project.total_chapters > 0
                ? Math.round((completed / project.total_chapters) * 100)
                : 0;
              return (
                <Card
                  key={project.project_id}
                  className="cursor-pointer transition-colors hover:border-primary/30"
                  onClick={() => navigate(`/projects/${encodeURIComponent(project.project_id)}/write`)}
                >
                  <CardHeader className="pb-2">
                    <div className="flex items-start justify-between gap-2">
                      <CardTitle className="line-clamp-1 text-base">{project.name}</CardTitle>
                      <span className="shrink-0 text-xs font-medium text-primary">继续写</span>
                    </div>
                    <CardDescription>
                      {project.genre} · {project.platform} · {completed} / {project.total_chapters} 章
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    <LiquidProgress value={pct} size="sm" showLabel />
                  </CardContent>
                </Card>
              );
            })}
          </div>
        </section>
      )}

      {/* Recent projects */}
      {recentProjects.length > 0 && (
        <section className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold">最近项目</h2>
            {projects.length > 3 && (
              <Link to="/projects" className="flex items-center gap-1 text-xs text-muted-foreground transition-colors hover:text-primary">
                查看全部
                <ChevronRight className="size-3" />
              </Link>
            )}
          </div>
          <Card>
            <CardContent className="divide-y divide-border p-0">
              {recentProjects.map((project) => (
                <button
                  key={project.project_id}
                  onClick={() => navigate(`/projects/${encodeURIComponent(project.project_id)}/write`)}
                  className="flex w-full items-center justify-between px-6 py-4 text-left transition-colors hover:bg-muted/50"
                >
                  <div>
                    <div className="font-medium">{project.name}</div>
                    <div className="text-xs text-muted-foreground">
                      {project.completed_chapters ?? project.current_chapter} / {project.total_chapters} 章 · {project.status}
                    </div>
                  </div>
                  <ChevronRight className="size-4 text-muted-foreground" />
                </button>
              ))}
            </CardContent>
          </Card>
        </section>
      )}

      {/* Empty / CTA */}
      {projects.length === 0 && !projectsLoading && (
        <Card className="border-dashed p-8 text-center">
          <div className="mx-auto mb-4 flex size-16 items-center justify-center rounded-full bg-primary/10 ring-1 ring-primary/20">
            <Sparkles className="size-8 text-primary" />
          </div>
          <h3 className="text-xl font-semibold">开始创作</h3>
          <p className="mx-auto mt-2 max-w-md text-sm text-muted-foreground">
            选择一个方向，让 AI 帮你完成从选题到成书的全过程
          </p>
          <div className="mt-6 flex justify-center gap-3">
            <Button asChild>
              <Link to="/create/category">
                <PlusCircle className="size-4" />
                新建项目
              </Link>
            </Button>
            <Button variant="outline" asChild>
              <Link to="/settings/llm">
                <Settings className="size-4" />
                配置 LLM
              </Link>
            </Button>
          </div>
        </Card>
      )}
    </div>
  );
}
