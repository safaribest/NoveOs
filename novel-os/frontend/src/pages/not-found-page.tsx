import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Home, ArrowLeft } from "lucide-react";

export function NotFoundPage() {
  return (
    <div className="flex min-h-[calc(100dvh-3.5rem)] flex-col items-center justify-center p-8 text-center">
      <h1 className="text-8xl font-bold tracking-tighter text-foreground/20 sm:text-9xl">
        404
      </h1>
      <h2 className="mt-6 text-2xl font-semibold tracking-tight">页面迷失在虚空之中</h2>
      <p className="mt-2 max-w-md text-muted-foreground">
        你寻找的页面不存在或尚未实现。让我们回到熟悉的地方继续创作。
      </p>
      <div className="mt-8 flex flex-wrap justify-center gap-3">
        <Button asChild>
          <Link to="/">
            <Home className="mr-2 size-4" />
            返回首页
          </Link>
        </Button>
        <Button variant="outline" onClick={() => window.history.back()}>
          <ArrowLeft className="mr-2 size-4" />
          返回上一页
        </Button>
      </div>
    </div>
  );
}
