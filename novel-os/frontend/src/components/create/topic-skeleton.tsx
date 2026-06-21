import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

export function TopicSkeleton() {
  return (
    <Card>
      <CardHeader className="pb-3">
        <Skeleton className="h-6 w-3/4" />
        <Skeleton className="mt-2 h-4 w-full" />
      </CardHeader>
      <CardContent className="space-y-4 pt-0">
        <Skeleton className="h-4 w-1/2" />
        <div className="space-y-2">
          <Skeleton className="h-3 w-full" />
          <Skeleton className="h-3 w-full" />
          <Skeleton className="h-3 w-2/3" />
        </div>
        <Skeleton className="h-16 w-full" />
        <Skeleton className="h-10 w-full" />
      </CardContent>
    </Card>
  );
}
