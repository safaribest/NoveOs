import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import type { ButtonProps } from "@/components/ui/button";

interface GlowButtonProps extends ButtonProps {
  glowColor?: "primary" | "aurora" | "accent";
}

export function GlowButton({
  className,
  glowColor = "primary",
  children,
  ...props
}: GlowButtonProps) {
  const colorMap = {
    primary: "hover:shadow-[0_0_30px_-5px_var(--color-primary)]",
    aurora: "hover:shadow-[0_0_30px_-5px_var(--color-aurora-2)]",
    accent: "hover:shadow-[0_0_30px_-5px_var(--color-aurora-3)]",
  };

  return (
    <Button
      className={cn(
        "relative overflow-hidden transition-all duration-300",
        "before:absolute before:inset-0 before:-translate-x-full before:bg-gradient-to-r before:from-transparent before:via-white/20 before:to-transparent before:transition-transform before:duration-700 hover:before:translate-x-full",
        colorMap[glowColor],
        className
      )}
      {...props}
    >
      {children}
    </Button>
  );
}
