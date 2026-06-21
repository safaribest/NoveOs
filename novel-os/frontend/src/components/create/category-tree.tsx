import { cn } from "@/lib/utils";
import { ChevronRight } from "lucide-react";
import type { Category } from "@/types/insight";

interface CategoryTreeProps {
  categories: Category[];
  selectedId: string;
  onSelect: (id: string) => void;
}

export function CategoryTree({ categories, selectedId, onSelect }: CategoryTreeProps) {
  return (
    <div className="space-y-1">
      {categories.map((level1) => (
        <div key={level1.id}>
          <div className="px-3 py-2 text-xs font-medium text-muted-foreground">
            {level1.name}
          </div>
          <div className="space-y-0.5">
            {level1.children?.map((level2) => (
              <div key={level2.id}>
                <button
                  type="button"
                  onClick={() => onSelect(level2.id)}
                  className={cn(
                    "flex w-full items-center justify-between rounded-md px-3 py-2 text-sm transition-colors",
                    selectedId === level2.id || level2.children?.some((c) => c.id === selectedId)
                      ? "bg-primary/10 text-primary"
                      : "text-muted-foreground hover:bg-secondary hover:text-foreground"
                  )}
                >
                  <span>{level2.name}</span>
                  <ChevronRight className="size-4" />
                </button>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
