import { cn } from "@/lib/utils";

interface GradientTextProps {
  children: React.ReactNode;
  className?: string;
  variant?: "gradient" | "shiny";
  as?: "span" | "h1" | "h2" | "h3" | "p";
}

export function GradientText({
  children,
  className,
  variant = "gradient",
  as: Component = "span",
}: GradientTextProps) {
  return (
    <Component
      className={cn(
        variant === "gradient" && "gradient-text",
        variant === "shiny" && "shiny-text",
        className
      )}
    >
      {children}
    </Component>
  );
}
