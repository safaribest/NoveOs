import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import type { Topic } from "@/types/insight";
import { Zap, Users, AlertTriangle, TrendingUp, ArrowRight, Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";

interface TopicCardProps {
  topic: Topic;
  onSelect: () => void;
  isRecommended?: boolean;
}

export function TopicCard({ topic, onSelect, isRecommended = false }: TopicCardProps) {
  return (
    <Card
      className={cn(
        "flex h-full flex-col transition-colors hover:border-primary/30",
        isRecommended && "border-primary ring-1 ring-primary/20"
      )}
    >
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-2 min-w-0">
            {isRecommended && (
              <Badge variant="default" className="shrink-0 gap-1 text-[10px]">
                <Sparkles className="size-3" />
                推荐
              </Badge>
            )}
            <CardTitle className="text-lg leading-tight truncate">{topic.title}</CardTitle>
          </div>
        </div>
        <p className="mt-2 text-sm text-muted-foreground">{topic.hook}</p>
      </CardHeader>
      <CardContent className="flex flex-1 flex-col gap-4 pt-0">
        <Separator />

        <div>
          <div className="mb-2 flex items-center gap-2 text-xs font-medium text-primary">
            <Zap className="size-3.5" />
            核心爽点
          </div>
          <ul className="space-y-1.5">
            {topic.slap_points.slice(0, 3).map((point, i) => (
              <li key={i} className="flex gap-2 text-sm text-muted-foreground">
                <span className="text-primary">•</span>
                <span>{point}</span>
              </li>
            ))}
          </ul>
        </div>

        <div>
          <div className="mb-2 flex items-center gap-2 text-xs font-medium text-muted-foreground">
            <Users className="size-3.5" />
            目标读者
          </div>
          <p className="text-sm text-muted-foreground">{topic.target_reader}</p>
        </div>

        <div>
          <div className="mb-2 flex items-center gap-2 text-xs font-medium text-destructive">
            <AlertTriangle className="size-3.5" />
            风险红线
          </div>
          <div className="flex flex-wrap gap-1.5">
            {topic.risks.map((risk, i) => (
              <Badge key={`${risk}-${i}`} variant="destructive" className="text-[10px]">
                {risk}
              </Badge>
            ))}
          </div>
        </div>

        <div className="mt-auto rounded-md bg-secondary/50 p-3">
          <div className="mb-1 flex items-center gap-2 text-xs font-medium text-primary">
            <TrendingUp className="size-3.5" />
            为什么现在能火
          </div>
          <p className="text-xs text-muted-foreground">{topic.why_now}</p>
        </div>

        <Button onClick={onSelect} className="w-full">
          选这个
          <ArrowRight className="ml-2 size-4" />
        </Button>
      </CardContent>
    </Card>
  );
}
