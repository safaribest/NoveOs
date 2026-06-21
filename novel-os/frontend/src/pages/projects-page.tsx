import { useEffect, useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { PlusCircle, BookOpen, AlertCircle, Pencil, Trash2, Sparkles } from "lucide-react";
import { Link } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { listProjects, updateProject, deleteProject, type ProjectStatus } from "@/api/projects";
import { Badge } from "@/components/ui/badge";
import { toast } from "@/lib/toast";
import { LiquidProgress } from "@/components/design/liquid-progress";

const PLATFORM_OPTIONS = [
  { value: "起点", label: "起点" },
  { value: "番茄", label: "番茄" },
  { value: "七猫", label: "七猫" },
  { value: "晋江", label: "晋江" },
];

function EmptyState() {
  return (
    <Card className="border-dashed p-12 text-center">
      <div className="mx-auto mb-4 flex size-16 items-center justify-center rounded-full bg-primary/10 ring-1 ring-primary/20">
        <Sparkles className="size-8 text-primary" />
      </div>
      <h3 className="text-xl font-semibold">暂无项目</h3>
      <p className="mx-auto mt-2 max-w-md text-sm text-muted-foreground">
        点击右上角按钮创建你的第一个项目，开启 AI 辅助创作之旅
      </p>
      <div className="mt-6">
        <Button asChild>
          <Link to="/create">
            <PlusCircle className="size-4" />
            去创建
          </Link>
        </Button>
      </div>
    </Card>
  );
}

function ErrorState({ error, onRetry }: { error: Error | null; onRetry: () => void }) {
  return (
    <Card className="border-destructive/30 p-8 text-center">
      <div className="mx-auto mb-4 flex size-12 items-center justify-center rounded-full bg-destructive/10 text-destructive">
        <AlertCircle className="size-6" />
      </div>
      <h3 className="text-lg font-semibold">加载项目失败</h3>
      <p className="mt-2 text-sm text-muted-foreground">
        {error?.message || "未知错误"}
      </p>
      <Button variant="outline" className="mt-4" onClick={onRetry}>
        重试
      </Button>
    </Card>
  );
}

export function ProjectsPage() {
  const queryClient = useQueryClient();
  const { data: projects = [], isLoading, error, refetch } = useQuery({
    queryKey: ["projects"],
    queryFn: listProjects,
    staleTime: 0,
    refetchOnMount: "always",
  });

  const [editingProject, setEditingProject] = useState<ProjectStatus | null>(null);
  const [deletingProject, setDeletingProject] = useState<ProjectStatus | null>(null);
  const [form, setForm] = useState({ name: "", genre: "", platform: "起点", chapters_target: 200, words_per_chapter: 2200 });
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [formError, setFormError] = useState("");
  const [deleteError, setDeleteError] = useState("");
  const [lastEditingProject, setLastEditingProject] = useState<ProjectStatus | null>(null);

  const initialForm = useMemo(() => {
    if (!editingProject) {
      return { name: "", genre: "", platform: "起点", chapters_target: 200, words_per_chapter: 2200 };
    }
    return {
      name: editingProject.name,
      genre: editingProject.genre,
      platform: editingProject.platform,
      chapters_target: editingProject.total_chapters,
      words_per_chapter: 2200,
    };
  }, [editingProject]);

  useEffect(() => {
    if (editingProject?.project_id !== lastEditingProject?.project_id) {
      queueMicrotask(() => {
        setLastEditingProject(editingProject);
        setForm(initialForm);
        setFormError("");
      });
    }
  }, [editingProject, lastEditingProject, initialForm]);

  const handleSave = async () => {
    if (!editingProject) return;
    if (!form.name.trim()) {
      setFormError("项目名称不能为空");
      return;
    }
    if (form.chapters_target < 3 || form.chapters_target > 2000) {
      setFormError("目标章数需在 3~2000 之间");
      return;
    }
    if (form.words_per_chapter < 500 || form.words_per_chapter > 10000) {
      setFormError("每章字数需在 500~10000 之间");
      return;
    }

    setSaving(true);
    setFormError("");
    try {
      await updateProject(editingProject.project_id, {
        name: form.name.trim(),
        genre: form.genre.trim() || "都市",
        platform: form.platform,
        chapters_target: form.chapters_target,
        words_per_chapter: form.words_per_chapter,
      });
      await queryClient.invalidateQueries({ queryKey: ["projects"] });
      setEditingProject(null);
      toast.success("项目已保存");
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "保存失败");
      toast.error(err instanceof Error ? err.message : "保存失败");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!deletingProject) return;
    setDeleting(true);
    setDeleteError("");
    try {
      await toast.promise(
        deleteProject(deletingProject.project_id, true).then(async () => {
          await queryClient.invalidateQueries({ queryKey: ["projects"] });
          setDeletingProject(null);
        }),
        {
          loading: "正在删除项目...",
          success: "项目已删除",
          error: (err: unknown) => (err instanceof Error ? err.message : "删除失败"),
        }
      );
    } catch (err) {
      setDeleteError(err instanceof Error ? err.message : "删除失败");
    } finally {
      setDeleting(false);
    }
  };

  return (
    <div className="space-y-6 p-8">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">
            项目列表
          </h1>
          <p className="text-sm text-muted-foreground">所有网文项目</p>
        </div>
        <Button asChild size="sm">
          <Link to="/create">
            <PlusCircle className="size-4" />
            新建项目
          </Link>
        </Button>
      </div>

      {isLoading ? (
        <div className="grid gap-4 md:grid-cols-2">
          {Array.from({ length: 4 }).map((_, i) => (
            <Card key={i} className="h-40 animate-pulse" />
          ))}
        </div>
      ) : error ? (
        <ErrorState error={error} onRetry={() => refetch()} />
      ) : projects.length === 0 ? (
        <EmptyState />
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {projects.map((project) => {
            const completed = project.completed_chapters ?? project.current_chapter;
            const pct = project.total_chapters > 0
              ? Math.round((completed / project.total_chapters) * 100)
              : 0;
            return (
              <Card key={project.project_id} className="group transition-colors hover:border-primary/30">
                <CardHeader className="pb-2">
                  <div className="flex items-start justify-between gap-2">
                    <Link
                      to={`/projects/${encodeURIComponent(project.project_id)}/write`}
                      className="min-w-0 flex-1"
                    >
                      <CardTitle className="line-clamp-1 text-base transition-colors group-hover:text-primary">
                        {project.name}
                      </CardTitle>
                    </Link>
                    <BookOpen className="size-4 shrink-0 text-muted-foreground" />
                  </div>
                  <CardDescription className="line-clamp-1">
                    {project.genre} · {project.platform}
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <Link
                    to={`/projects/${encodeURIComponent(project.project_id)}/write`}
                    className="block"
                  >
                    <div className="flex items-center justify-between text-sm">
                      <Badge variant={project.status === "writing" ? "default" : "secondary"}>
                        {project.status === "writing" ? "写作中" : project.status}
                      </Badge>
                      <span className="text-muted-foreground">
                        {completed} / {project.total_chapters} 章
                      </span>
                    </div>
                    <div className="mt-3">
                      <LiquidProgress value={pct} size="sm" />
                    </div>
                  </Link>
                  <div className="flex justify-end gap-1">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setEditingProject(project)}
                    >
                      <Pencil className="mr-1 size-3" />
                      编辑
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="text-destructive hover:text-destructive"
                      onClick={() => setDeletingProject(project)}
                    >
                      <Trash2 className="mr-1 size-3" />
                      删除
                    </Button>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}

      <Dialog open={!!editingProject} onOpenChange={(open) => { if (!open) setEditingProject(null); }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>编辑项目</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>项目名称</Label>
              <Input
                value={form.name}
                onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                placeholder="项目名称"
              />
            </div>
            <div className="space-y-2">
              <Label>题材</Label>
              <Input
                value={form.genre}
                onChange={(e) => setForm((f) => ({ ...f, genre: e.target.value }))}
                placeholder="如：都市、玄幻"
              />
            </div>
            <div className="space-y-2">
              <Label>目标平台</Label>
              <Select
                value={form.platform}
                onValueChange={(value) => setForm((f) => ({ ...f, platform: value }))}
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
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>目标章数</Label>
                <Input
                  type="number"
                  min={3}
                  max={2000}
                  value={form.chapters_target}
                  onChange={(e) => {
                    const v = e.target.value;
                    setForm((f) => ({ ...f, chapters_target: v === "" ? 0 : Number(v) }));
                  }}
                />
              </div>
              <div className="space-y-2">
                <Label>每章字数</Label>
                <Input
                  type="number"
                  min={500}
                  max={10000}
                  value={form.words_per_chapter}
                  onChange={(e) => {
                    const v = e.target.value;
                    setForm((f) => ({ ...f, words_per_chapter: v === "" ? 0 : Number(v) }));
                  }}
                />
              </div>
            </div>
            {formError && (
              <div className="flex items-center gap-2 text-sm text-destructive">
                <AlertCircle className="size-4" />
                {formError}
              </div>
            )}
            <DialogFooter>
              <Button variant="outline" onClick={() => setEditingProject(null)} disabled={saving}>
                取消
              </Button>
              <Button onClick={handleSave} disabled={saving}>
                {saving ? "保存中..." : "保存"}
              </Button>
            </DialogFooter>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={!!deletingProject} onOpenChange={(open) => { if (!open) setDeletingProject(null); }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>确认删除项目</DialogTitle>
            <DialogDescription>
              确定要删除项目 <span className="font-semibold text-foreground">{deletingProject?.name}</span> 吗？
              该项目下的所有章节、大纲与状态数据都会被一并删除，且不可恢复。
            </DialogDescription>
          </DialogHeader>
          {deletingProject?.status === "writing" && (
            <div className="flex items-center gap-2 rounded-md bg-destructive/10 px-3 py-2 text-xs text-destructive">
              <AlertCircle className="size-4" />
              该项目当前处于写作中，删除会先停止流水线。
            </div>
          )}
          {deleteError && (
            <div className="flex items-center gap-2 text-sm text-destructive">
              <AlertCircle className="size-4" />
              {deleteError}
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeletingProject(null)} disabled={deleting}>
              取消
            </Button>
            <Button variant="destructive" onClick={handleDelete} disabled={deleting}>
              {deleting ? "删除中..." : "确认删除"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
