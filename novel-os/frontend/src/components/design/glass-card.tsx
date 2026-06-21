import { cn } from "@/lib/utils";

interface GlassCardProps extends React.HTMLAttributes<HTMLDivElement> {
  hover?: boolean;
  glow?: boolean;
  elevated?: boolean;
}

export function GlassCard({
  className,
  children,
  hover = true,
  glow = false,
  elevated = false,
  ...props
}: GlassCardProps) {
  return (
    <div
      className={cn(
        "rounded-xl border border-glass-border bg-glass/80 text-card-foreground shadow-glass backdrop-blur-glass transition-all duration-200",
        hover && "hover:-translate-y-0.5 hover:border-border-hover hover:shadow-lg",
        glow && "glow-border",
        elevated && "bg-glass-bg/90 shadow-lg",
        className
      )}
      {...props}
    >
      {children}
    </div>
  );
}
