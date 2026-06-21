import { useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { CategoryTree } from "@/components/create/category-tree";
import { CategoryCard } from "@/components/create/category-card";
import { getCategories } from "@/api/insights";
import type { Category } from "@/types/insight";
import { Sparkles, ArrowRight } from "lucide-react";

function findCategoryById(categories: Category[], id: string): Category | null {
  for (const c of categories) {
    if (c.id === id) return c;
    if (c.children) {
      const found = findCategoryById(c.children, id);
      if (found) return found;
    }
  }
  return null;
}

function getLeafCategories(categories: Category[], parentId: string): Category[] {
  const parent = findCategoryById(categories, parentId);
  if (!parent) return [];
  return parent.children?.filter((c) => !c.children) || [];
}

export function CategoryPage() {
  const navigate = useNavigate();
  const [selectedLevel2, setSelectedLevel2] = useState<string>("");
  const [selectedLevel3, setSelectedLevel3] = useState<string>("");

  const { data: categories = [], isLoading, error } = useQuery({
    queryKey: ["categories"],
    queryFn: getCategories,
  });

  const level2Categories = useMemo(() => {
    return categories.flatMap((c) => c.children || []);
  }, [categories]);

  const leafCategories = useMemo(() => {
    return selectedLevel2 ? getLeafCategories(categories, selectedLevel2) : [];
  }, [categories, selectedLevel2]);

  const selectedCategory = useMemo(() => {
    return selectedLevel3 ? findCategoryById(categories, selectedLevel3) : null;
  }, [categories, selectedLevel3]);

  const handleLevel2Select = (id: string) => {
    setSelectedLevel2(id);
    setSelectedLevel3("");
  };

  const handleGenerate = () => {
    if (!selectedLevel3) return;
    navigate(`/create/topics?category=${selectedLevel3}`);
  };

  return (
    <div className="space-y-6 p-8">
      <div>
        <h1 className="text-2xl font-bold">选择创作方向</h1>
        <p className="text-sm text-muted-foreground">选择分类后，AI 会为你生成多个爆款选题</p>
        <p className="text-xs text-muted-foreground mt-1">
          调试：isLoading={String(isLoading)} error={error ? (error instanceof Error ? error.message : String(error)) : "无"} categories.length={categories.length}
        </p>
      </div>

      <div>
        {isLoading ? (
          <div className="grid gap-4 md:grid-cols-3">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-32 animate-pulse rounded-lg bg-muted/30" />
            ))}
          </div>
        ) : (
          <div className="grid gap-6 lg:grid-cols-12">
            <Card className="lg:col-span-3">
              <CardHeader>
                <CardTitle className="text-base">分类</CardTitle>
              </CardHeader>
              <CardContent className="overflow-y-auto pt-0" style={{ maxHeight: "calc(100vh - 18rem)" }}>
                <CategoryTree
                  categories={categories}
                  selectedId={selectedLevel2}
                  onSelect={handleLevel2Select}
                />
              </CardContent>
            </Card>

            <div className="lg:col-span-9 max-h-[calc(100vh-12rem)] overflow-y-auto">
              {!selectedLevel2 ? (
                <Card className="flex h-96 flex-col items-center justify-center border-dashed">
                  <div className="flex h-16 w-16 items-center justify-center rounded-full bg-primary/10">
                    <Sparkles className="size-8 text-primary" />
                  </div>
                  <h3 className="mt-4 text-lg font-semibold">先选择一个分类</h3>
                  <p className="mt-1 text-sm text-muted-foreground">
                    从左侧选择男频/女频下的二级分类
                  </p>
                </Card>
              ) : (
                <>
                  <div className="mb-4 flex items-center justify-between">
                    <div>
                      <h2 className="text-lg font-semibold">
                        {level2Categories.find((c) => c.id === selectedLevel2)?.name}
                      </h2>
                      <p className="text-sm text-muted-foreground">
                        选择具体方向，生成选题
                      </p>
                    </div>
                    {selectedLevel3 && (
                      <Button onClick={handleGenerate}>
                        生成选题
                        <ArrowRight className="ml-2 size-4" />
                      </Button>
                    )}
                  </div>

                  <div className="grid gap-4 sm:grid-cols-2">
                    {leafCategories.map((category) => (
                      <CategoryCard
                        key={category.id}
                        name={category.name}
                        genre={category.genre}
                        tags={category.tags}
                        selected={selectedLevel3 === category.id}
                        onClick={() => setSelectedLevel3(category.id)}
                      />
                    ))}
                  </div>

                  {selectedCategory && (
                    <Card className="mt-6 border-primary/20 bg-primary/5">
                      <CardContent className="flex items-center justify-between py-4">
                        <div>
                          <p className="font-medium">已选择：{selectedCategory.name}</p>
                          <p className="text-sm text-muted-foreground">
                            {selectedCategory.tags?.join(" / ")}
                          </p>
                        </div>
                        <Button onClick={handleGenerate}>
                          生成选题
                          <ArrowRight className="ml-2 size-4" />
                        </Button>
                      </CardContent>
                    </Card>
                  )}
                </>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
