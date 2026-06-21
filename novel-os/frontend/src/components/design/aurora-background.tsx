import { cn } from "@/lib/utils";

interface AuroraBackgroundProps {
  children?: React.ReactNode;
  className?: string;
  intensity?: "subtle" | "soft" | "vivid";
  variant?: "full" | "top" | "bottom";
}

export function AuroraBackground({
  children,
  className,
  intensity = "soft",
  variant = "full",
}: AuroraBackgroundProps) {
  const intensityMap = {
    subtle: "opacity-30",
    soft: "opacity-50",
    vivid: "opacity-80",
  };

  const variantMap = {
    full: "inset-0",
    top: "inset-x-0 top-0 h-[60vh]",
    bottom: "inset-x-0 bottom-0 h-[60vh]",
  };

  return (
    <div className={cn("relative isolate overflow-hidden", className)}>
      <div
        className={cn(
          "pointer-events-none absolute -z-10 blur-3xl",
          variantMap[variant],
          intensityMap[intensity]
        )}
        aria-hidden="true"
      >
        <div
          className={cn(
            "absolute inset-0 aurora-bg",
            variant === "top" && "bg-[radial-gradient(ellipse_at_50%_0%,var(--color-aurora-1)_0%,transparent_50%)]",
            variant === "bottom" && "bg-[radial-gradient(ellipse_at_50%_100%,var(--color-aurora-2)_0%,transparent_50%)]"
          )}
        />
      </div>
      <div className="absolute inset-0 -z-10 bg-background/80 backdrop-blur-[1px]" aria-hidden="true" />
      {children}
    </div>
  );
}
