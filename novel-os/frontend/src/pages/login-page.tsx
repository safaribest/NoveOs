import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { BookOpen, Loader2, AlertCircle, Sparkles } from "lucide-react";
import { useAuth } from "@/hooks/use-auth";
import { GradientText } from "@/components/design/gradient-text";
import { Card, CardContent } from "@/components/ui/card";

export function LoginPage() {
  const navigate = useNavigate();
  const { user, isLoading, error: authError, login, clearError } = useAuth();
  const [submitting, setSubmitting] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");

  const error = localError || authError;

  useEffect(() => {
    if (user) {
      navigate("/", { replace: true });
    }
  }, [user, navigate]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    clearError();
    setLocalError(null);

    if (!username.trim() || !password.trim()) {
      setLocalError("请输入用户名和密码");
      return;
    }

    setSubmitting(true);
    try {
      await login(username.trim(), password);
      navigate("/", { replace: true });
    } catch {
      // 错误已由 AuthContext 设置
    } finally {
      setSubmitting(false);
    }
  };

  if (isLoading) {
    return (
      <div className="flex min-h-[100dvh] items-center justify-center bg-background">
        <Loader2 className="size-8 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div className="flex min-h-[100dvh] items-center justify-center bg-background p-4">
      <div className="grid w-full max-w-5xl gap-8 lg:grid-cols-2 lg:items-center">
        {/* Brand section */}
        <div className="hidden flex-col justify-center space-y-6 lg:flex">
          <div className="flex items-center gap-3">
            <div className="flex size-12 items-center justify-center rounded-xl bg-primary/10 text-primary">
              <BookOpen className="size-6" />
            </div>
            <span className="text-xl font-bold tracking-tight">Novel-OS</span>
          </div>
          <div className="space-y-4">
            <h1 className="text-5xl font-bold leading-tight tracking-tight">
              <GradientText variant="gradient" className="font-display">
                让 AI 成为你的
              </GradientText>
              <br />
              写作搭档
            </h1>
            <p className="max-w-md text-lg text-muted-foreground">
              从选题、大纲到成书，Novel-OS 用智能流水线陪伴你完成每一部网文作品。
            </p>
          </div>
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Sparkles className="size-4 text-primary" />
            <span>智能选题 · 自动大纲 · 章节写作 · 质量门禁</span>
          </div>
        </div>

        {/* Login form */}
        <Card className="w-full max-w-sm mx-auto lg:mx-0 lg:ml-auto">
          <CardContent className="p-8">
          <div className="mb-6 text-center lg:hidden">
            <div className="mx-auto mb-4 flex size-12 items-center justify-center rounded-xl bg-primary/10 text-primary">
              <BookOpen className="size-6" />
            </div>
            <h2 className="text-2xl font-bold tracking-tight">Novel-OS</h2>
            <p className="text-sm text-muted-foreground">AI 小说写作系统</p>
          </div>

          <div className="mb-6 hidden lg:block">
            <h2 className="text-2xl font-bold tracking-tight">欢迎回来</h2>
            <p className="text-sm text-muted-foreground">登录以继续你的创作旅程</p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            {error && (
              <div className="flex items-center gap-2 rounded-lg border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive animate-fade-in">
                <AlertCircle className="size-4 shrink-0" />
                {error}
              </div>
            )}

            <div className="space-y-2">
              <Label htmlFor="username">用户名</Label>
              <Input
                id="username"
                type="text"
                placeholder="请输入用户名"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                disabled={submitting}
                autoComplete="username"
                className="bg-background"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="password">密码</Label>
              <Input
                id="password"
                type="password"
                placeholder="请输入密码"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                disabled={submitting}
                autoComplete="current-password"
                className="bg-background"
              />
            </div>

            <Button type="submit" className="w-full" disabled={submitting}>
              {submitting ? (
                <>
                  <Loader2 className="mr-2 size-4 animate-spin" />
                  登录中...
                </>
              ) : (
                "登录"
              )}
            </Button>
          </form>

          <div className="mt-6 flex items-center justify-between text-sm">
            <a href="#" className="text-muted-foreground transition-colors hover:text-primary">
              忘记密码？
            </a>
            <span className="text-muted-foreground/60">默认账号：admin / admin</span>
          </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
