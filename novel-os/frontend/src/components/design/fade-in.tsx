import { cn } from "@/lib/utils";

interface FadeInProps {
  children: React.ReactNode;
  className?: string;
  delay?: number;
  direction?: "up" | "down" | "left" | "right" | "none";
  duration?: "fast" | "normal" | "slow";
  distance?: number;
}

export function FadeIn({
  children,
  className,
  delay = 0,
  direction = "up",
  duration = "normal",
  distance = 12,
}: FadeInProps) {
  const durationMap = {
    fast: 0.2,
    normal: 0.35,
    slow: 0.5,
  };

  const animationName = direction === "none" ? "fade-in" : `fade-in-${direction}`;

  return (
    <div
      className={cn(className)}
      style={{
        animationName,
        animationDuration: `${durationMap[duration]}s`,
        animationDelay: `${delay}s`,
        animationFillMode: "both",
        animationTimingFunction: "cubic-bezier(0.16, 1, 0.3, 1)",
        opacity: 0,
        ["--fade-distance" as string]: `${distance}px`,
      }}
    >
      {children}
    </div>
  );
}

interface StaggerContainerProps {
  children: React.ReactNode;
  className?: string;
  stagger?: number;
}

export function StaggerContainer({ children, className, stagger = 0.05 }: StaggerContainerProps) {
  return (
    <div
      className={cn("stagger-container", className)}
      style={{ "--stagger": `${stagger}s` } as React.CSSProperties}
    >
      {children}
    </div>
  );
}
