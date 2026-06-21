import { cn } from "@/lib/utils";

interface LiquidProgressProps {
  value: number;
  max?: number;
  className?: string;
  barClassName?: string;
  showLabel?: boolean;
  size?: "sm" | "md" | "lg";
}

export function LiquidProgress({
  value,
  max = 100,
  className,
  barClassName,
  showLabel = false,
  size = "md",
}: LiquidProgressProps) {
  const percentage = Math.min(100, Math.max(0, (value / max) * 100));

  const sizeMap = {
    sm: "h-1.5",
    md: "h-2.5",
    lg: "h-4",
  };

  return (
    <div className={cn("w-full", className)}>
      <div
        className={cn(
          "relative w-full overflow-hidden rounded-full bg-secondary",
          sizeMap[size]
        )}
        role="progressbar"
        aria-valuenow={Math.round(percentage)}
        aria-valuemin={0}
        aria-valuemax={100}
      >
        <div
          className={cn(
            "relative h-full overflow-hidden rounded-full bg-primary transition-all duration-500 ease-out",
            barClassName
          )}
          style={{ width: `${percentage}%` }}
        >
        </div>
      </div>
      {showLabel && (
        <p className="mt-1.5 text-xs font-medium text-muted-foreground">
          {Math.round(percentage)}%
        </p>
      )}
    </div>
  );
}
