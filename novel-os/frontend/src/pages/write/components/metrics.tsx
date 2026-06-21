import { formatNumber } from "./utils";

interface MetricItemProps {
  label: string;
  value?: number | null;
  suffix?: string;
}

export function MetricItem({ label, value, suffix = "" }: MetricItemProps) {
  const display = value == null ? "--" : `${formatNumber(value)}${suffix}`;
  return (
    <div className="flex flex-col">
      <span className="text-lg font-semibold tracking-tight">{display}</span>
      <span className="text-xs text-muted-foreground">{label}</span>
    </div>
  );
}

interface SmallMetricProps {
  label: string;
  value?: number | null;
}

export function SmallMetric({ label, value }: SmallMetricProps) {
  const display = value == null ? "--" : String(value);
  return (
    <div className="flex flex-col">
      <span className="text-sm font-semibold text-foreground">{display}</span>
      <span className="text-[10px] text-muted-foreground">{label}</span>
    </div>
  );
}
