import { cn } from "@/lib/utils";
import { Check } from "lucide-react";

interface CategoryCardProps {
  name: string;
  genre?: string;
  tags?: string[];
  selected: boolean;
  onClick: () => void;
  variant?: "default" | "ghost";
}

export function CategoryCard({
  name,
  genre,
  tags,
  selected,
  onClick,
  variant = "default",
}: CategoryCardProps) {
  const isGhost = variant === "ghost";

  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "relative flex w-full flex-col items-start rounded-xl p-4 text-left transition-all duration-200",
        isGhost
          ? "bg-transparent hover:bg-primary/5"
          : "rounded-xl border hover:-translate-y-0.5 hover:border-primary/50 hover:bg-card-hover hover:shadow-md",
        !isGhost && (selected
          ? "border-primary bg-primary/5"
          : "border-border bg-card"),
        isGhost && selected && "bg-primary/5"
      )}
    >
      {selected && (
        <div className="absolute right-3 top-3 flex h-5 w-5 items-center justify-center rounded-full bg-primary text-primary-foreground shadow-sm">
          <Check className="size-3" />
        </div>
      )}
      <span className="text-base font-semibold">{name}</span>
      {genre && genre !== name && (
        <span className="mt-1 text-xs text-muted-foreground">{genre}</span>
      )}
      {tags && tags.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {tags.slice(0, 3).map((tag) => (
            <span
              key={tag}
              className="rounded-full bg-secondary/80 px-2 py-0.5 text-[10px] text-muted-foreground"
            >
              {tag}
            </span>
          ))}
        </div>
      )}
    </button>
  );
}
