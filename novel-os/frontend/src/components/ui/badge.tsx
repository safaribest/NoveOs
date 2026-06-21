import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium backdrop-blur-md transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2",
  {
    variants: {
      variant: {
        default: "border-transparent bg-primary/15 text-primary hover:bg-primary/20",
        secondary: "border-transparent bg-glass/70 text-secondary-foreground hover:bg-glass",
        destructive: "border-transparent bg-destructive/15 text-destructive hover:bg-destructive/20",
        outline: "text-foreground border-glass-border bg-glass/50 hover:bg-glass",
        success: "border-transparent bg-success/15 text-success hover:bg-success/20",
        warning: "border-transparent bg-warning/15 text-warning hover:bg-warning/20",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

export function Badge({ className, variant, ...props }: BadgeProps) {
  return (
    <div className={cn(badgeVariants({ variant, className }))} {...props} />
  );
}
