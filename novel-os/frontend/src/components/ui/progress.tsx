import { cn } from "@/lib/utils";

export interface ProgressProps extends React.HTMLAttributes<HTMLDivElement> {
  value: number;
  max?: number;
  showValue?: boolean;
}

export function Progress({
  className,
  value,
  max = 100,
  showValue = false,
  ...props
}: ProgressProps) {
  const percentage = Math.min(100, Math.max(0, (value / max) * 100));

  return (
    <div
      className={cn("flex items-center gap-3", className)}
      {...props}
    >
      <div className="relative h-2 w-full overflow-hidden rounded-full bg-secondary">
        <div
          className="h-full rounded-full bg-primary transition-all duration-300"
          style={{ width: `${percentage}%` }}
        />
      </div>
      {showValue && (
        <span className="min-w-[3rem] text-right text-xs text-muted-foreground">
          {Math.round(percentage)}%
        </span>
      )}
    </div>
  );
}
