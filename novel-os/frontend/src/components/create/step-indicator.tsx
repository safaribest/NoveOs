import { useLocation, Link } from "react-router-dom";
import { Check } from "lucide-react";
import { cn } from "@/lib/utils";

const steps = [
  { label: "分类选择", path: "/create/category" },
  { label: "选题推荐", path: "/create/topics" },
  { label: "大纲生成", path: "/create/outline" },
  { label: "确认创建", path: "/create/confirm" },
];

export function StepIndicator() {
  const location = useLocation();
  const currentIndex = steps.findIndex((s) => location.pathname.startsWith(s.path));

  return (
    <div className="border-b border-border bg-background px-4 py-4">
      <div className="mx-auto flex max-w-3xl items-center justify-between rounded-full border border-border bg-card p-1.5">
        {steps.map((step, i) => {
          const isCurrent = i === currentIndex;
          const isClickable = i < currentIndex;

          return (
            <div key={step.path} className="flex flex-1 items-center">
              {isClickable ? (
                <Link
                  to={step.path}
                  className={cn(
                    "group flex flex-1 items-center justify-center gap-2 rounded-full px-3 py-2 text-xs font-medium transition-all",
                    "text-muted-foreground hover:bg-primary/10 hover:text-primary"
                  )}
                >
                  <span className="flex size-5 items-center justify-center rounded-full bg-primary/15 text-primary transition-colors group-hover:bg-primary group-hover:text-primary-foreground">
                    <Check className="size-3" />
                  </span>
                  <span className="hidden sm:inline">{step.label}</span>
                </Link>
              ) : (
                <span
                  className={cn(
                    "flex flex-1 items-center justify-center gap-2 rounded-full px-3 py-2 text-xs font-medium transition-all",
                    isCurrent
                      ? "bg-primary text-primary-foreground"
                      : "text-muted-foreground"
                  )}
                >
                  <span
                    className={cn(
                      "flex size-5 items-center justify-center rounded-full text-[10px] font-semibold",
                      isCurrent
                        ? "bg-primary-foreground text-primary"
                        : "bg-muted text-muted-foreground"
                    )}
                  >
                    {i + 1}
                  </span>
                  <span className="hidden sm:inline">{step.label}</span>
                </span>
              )}
              {i < steps.length - 1 && (
                <span
                  className={cn(
                    "mx-1 h-px w-4 shrink-0",
                    i < currentIndex ? "bg-primary/40" : "bg-border"
                  )}
                />
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
