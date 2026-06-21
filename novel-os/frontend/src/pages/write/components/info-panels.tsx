import { CircularProgress, DonutChart } from "./charts";
import { SmallMetric } from "./metrics";
import { AgentStatusCard, AGENT_ORDER } from "./agent-status-card";

interface InfoPanelsProps {
  currentAgentName: string | undefined;
  qualityScore: number | null;
  qualityMetrics: { label: string; value: number | null }[];
  isLoadingQuality: boolean;
  wordCount: number;
  inputWordCount: number;
  wordGoal: number;
}

const thinScrollbarStyle: React.CSSProperties = {
  scrollbarWidth: "thin",
  scrollbarColor: "var(--color-border) transparent",
};

export function InfoPanels({
  currentAgentName,
  qualityScore,
  qualityMetrics,
  isLoadingQuality,
  wordCount,
  inputWordCount,
  wordGoal,
}: InfoPanelsProps) {
  const wordCountSegments = [
    { value: wordCount, color: "var(--color-primary)" },
    { value: Math.max(0, wordGoal - wordCount), color: "var(--color-muted)" },
  ];

  return (
    <aside
      className="flex w-[300px] shrink-0 flex-col gap-4 overflow-y-auto rounded-xl border border-border bg-card p-4 max-md:w-full"
      style={thinScrollbarStyle}
    >
      {/* Agent 状态 */}
      <div className="rounded-xl border border-border/50 bg-background/50 p-3">
        <h3 className="mb-2 text-xs font-medium text-muted-foreground">
          Agent 状态
        </h3>
        <div className="space-y-2">
          {AGENT_ORDER.map((agent) => (
            <AgentStatusCard
              key={agent}
              name={agent}
              status={currentAgentName === agent ? "running" : "idle"}
            />
          ))}
        </div>
      </div>

      {/* 本章质量门禁 */}
      <div
        className={`rounded-xl border border-border/50 bg-background/50 p-3 transition-opacity ${
          isLoadingQuality ? "opacity-60" : "opacity-100"
        }`}
      >
        <h3 className="mb-3 text-xs font-medium text-muted-foreground">
          本章质量门禁
        </h3>
        <div className="flex items-center gap-4">
          <CircularProgress value={qualityScore ?? 0} size={72} strokeWidth={6}>
            <span className="text-lg font-bold text-foreground">{qualityScore ?? "--"}</span>
          </CircularProgress>
          <div className="grid grid-cols-2 gap-x-6 gap-y-2">
            {qualityMetrics.map((m) => (
              <SmallMetric key={m.label} label={m.label} value={m.value} />
            ))}
          </div>
        </div>
      </div>

      {/* 字数统计 */}
      <div className="rounded-xl border border-border/50 bg-background/50 p-3">
        <h3 className="mb-3 text-xs font-medium text-muted-foreground">
          字数统计
        </h3>
        <div className="flex items-center gap-4">
          <DonutChart segments={wordCountSegments} size={80} strokeWidth={10} />
          <div className="grid grid-cols-2 gap-x-6 gap-y-2">
            <SmallMetric label="本章字数" value={wordCount} />
            <SmallMetric label="输入字数" value={inputWordCount} />
            <SmallMetric label="AI生成" value={wordCount} />
            <SmallMetric label="目标字数" value={wordGoal || null} />
          </div>
        </div>
      </div>
    </aside>
  );
}
