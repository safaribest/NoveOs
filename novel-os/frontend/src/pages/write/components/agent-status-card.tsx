import {
  Target,
  Zap,
  Feather,
  Sparkles,
  Users,
  Search as SearchIcon,
  BarChart3,
} from "lucide-react";

const AGENT_DISPLAY_MAP: Record<string, { icon: React.ReactNode; label: string; color: string }> = {
  director: { icon: <Target className="size-3.5" />, label: "规划师 Planner", color: "text-blue-500" },
  beat_planner: { icon: <Zap className="size-3.5" />, label: "情节师 Plotter", color: "text-amber-500" },
  scene_writer: { icon: <Feather className="size-3.5" />, label: "文笔师 Stylist", color: "text-purple-500" },
  hook_engineer: { icon: <Sparkles className="size-3.5" />, label: "追读力评估师", color: "text-pink-500" },
  dialogue_tuner: { icon: <Users className="size-3.5" />, label: "对话调优师", color: "text-cyan-500" },
  polish: { icon: <Sparkles className="size-3.5" />, label: "润色师", color: "text-indigo-500" },
  auditor: { icon: <SearchIcon className="size-3.5" />, label: "质检员 Reviewer", color: "text-rose-500" },
  expander: { icon: <BarChart3 className="size-3.5" />, label: "扩写师", color: "text-orange-500" },
  BatchWriter: { icon: <Zap className="size-3.5" />, label: "构建", color: "text-emerald-500" },
};

export const AGENT_ORDER = ["director", "beat_planner", "scene_writer", "auditor", "hook_engineer"];

interface AgentStatusCardProps {
  name: string;
  status: "idle" | "running";
}

export function AgentStatusCard({ name, status }: AgentStatusCardProps) {
  const mapping = AGENT_DISPLAY_MAP[name] || {
    icon: <Zap className="size-3.5" />,
    label: name,
    color: "text-muted-foreground",
  };
  const isRunning = status === "running";

  return (
    <div className="flex items-center justify-between rounded-lg border border-border/60 bg-secondary/30 px-3 py-2.5">
      <div className="flex items-center gap-2.5">
        <div className={`flex size-7 items-center justify-center rounded-md bg-secondary/80 ${mapping.color}`}>
          {mapping.icon}
        </div>
        <span className="text-sm font-medium">{mapping.label}</span>
      </div>
      <div className="flex items-center gap-1.5">
        {isRunning && <span className="size-1.5 rounded-full bg-primary animate-pulse" />}
        <span className={`text-xs ${isRunning ? "text-primary" : "text-muted-foreground"}`}>
          {isRunning ? "运行中" : "空闲"}
        </span>
      </div>
    </div>
  );
}
