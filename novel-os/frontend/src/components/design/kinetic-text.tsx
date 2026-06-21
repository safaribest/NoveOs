import { cn } from "@/lib/utils";

interface KineticTextProps {
  children: string;
  className?: string;
  as?: "h1" | "h2" | "h3" | "p" | "span";
  delay?: number;
  stagger?: number;
  duration?: "fast" | "normal" | "slow";
  variant?: "fade" | "rise" | "glow";
}

export function KineticText({
  children,
  className,
  as: Component = "span",
  delay = 0,
  stagger = 0.03,
  duration = "normal",
  variant = "rise",
}: KineticTextProps) {
  const durationMap = {
    fast: 0.25,
    normal: 0.4,
    slow: 0.6,
  };

  const chars = children.split("");

  return (
    <Component className={cn("inline-block", className)} aria-label={children}>
      {chars.map((char, i) => (
        <span
          key={`${char}-${i}`}
          className={cn(
            "inline-block will-change-transform",
            variant === "fade" && "animate-fade-in",
            variant === "rise" && "animate-fade-in-up",
            variant === "glow" && "animate-fade-in-up shiny-text"
          )}
          style={{
            animationDuration: `${durationMap[duration]}s`,
            animationDelay: `${delay + i * stagger}s`,
            animationFillMode: "both",
            animationTimingFunction: "cubic-bezier(0.16, 1, 0.3, 1)",
            opacity: 0,
            minWidth: char === " " ? "0.3em" : undefined,
          }}
        >
          {char === " " ? "\u00A0" : char}
        </span>
      ))}
    </Component>
  );
}
