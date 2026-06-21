import { useRef, useState } from "react";
import { cn } from "@/lib/utils";

interface SpotlightCardProps extends React.HTMLAttributes<HTMLDivElement> {
  hover?: boolean;
}

export function SpotlightCard({
  className,
  children,
  hover = true,
  ...props
}: SpotlightCardProps) {
  const ref = useRef<HTMLDivElement>(null);
  const [position, setPosition] = useState({ x: 0, y: 0 });
  const [opacity, setOpacity] = useState(0);

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!ref.current) return;
    const rect = ref.current.getBoundingClientRect();
    setPosition({
      x: e.clientX - rect.left,
      y: e.clientY - rect.top,
    });
  };

  const handleMouseEnter = () => setOpacity(1);
  const handleMouseLeave = () => setOpacity(0);

  return (
    <div
      ref={ref}
      onMouseMove={handleMouseMove}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      className={cn(
        "relative overflow-hidden rounded-xl border border-glass-border bg-glass/80 text-card-foreground shadow-glass backdrop-blur-glass transition-all duration-200",
        hover && "hover:-translate-y-0.5 hover:border-border-hover hover:shadow-lg",
        className
      )}
      {...props}
    >
      <div
        className="pointer-events-none absolute -inset-px transition-opacity duration-300"
        style={{
          opacity,
          background: `radial-gradient(600px circle at ${position.x}px ${position.y}px, var(--color-aurora-glow), transparent 40%)`,
        }}
        aria-hidden="true"
      />
      {children}
    </div>
  );
}
