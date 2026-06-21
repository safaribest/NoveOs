import * as React from "react";
import { cn } from "@/lib/utils";

export interface TextareaProps
  extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
  error?: string;
}

export const Textarea = React.forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ className, error, ...props }, ref) => (
    <textarea
      className={cn(
        "flex min-h-[80px] w-full rounded-xl border border-glass-border bg-glass/60 px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground backdrop-blur-md transition-all duration-200 focus-visible:border-ring focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/30 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50",
        error && "border-destructive focus-visible:ring-destructive/30",
        className
      )}
      ref={ref}
      {...props}
    />
  )
);
Textarea.displayName = "Textarea";
