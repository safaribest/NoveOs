interface CircularProgressProps {
  value: number;
  size?: number;
  strokeWidth?: number;
  children?: React.ReactNode;
}

export function CircularProgress({
  value,
  size = 64,
  strokeWidth = 5,
  children,
}: CircularProgressProps) {
  const safeValue = Math.max(0, Math.min(100, value));
  const radius = (size - strokeWidth) / 2;
  const circumference = radius * 2 * Math.PI;
  const offset = circumference - (safeValue / 100) * circumference;

  return (
    <div
      className="relative inline-flex items-center justify-center"
      style={{ width: size, height: size }}
    >
      <svg width={size} height={size} className="-rotate-90">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="currentColor"
          strokeWidth={strokeWidth}
          className="text-muted/30"
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="currentColor"
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          className="text-primary transition-all duration-500"
          style={{
            strokeDasharray: circumference,
            strokeDashoffset: offset,
          }}
        />
      </svg>
      <div className="absolute inset-0 flex items-center justify-center">{children}</div>
    </div>
  );
}

interface DonutChartProps {
  segments: { value: number; color: string }[];
  size?: number;
  strokeWidth?: number;
}

export function DonutChart({ segments, size = 96, strokeWidth = 10 }: DonutChartProps) {
  const radius = (size - strokeWidth) / 2;
  const circumference = radius * 2 * Math.PI;
  const total = segments.reduce((sum, s) => sum + s.value, 0);
  const prefix = segments.reduce<number[]>((acc, s, i) => {
    acc.push((acc[i - 1] ?? 0) + s.value);
    return acc;
  }, []);

  if (total <= 0) {
    return (
      <svg width={size} height={size} className="-rotate-90">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="currentColor"
          strokeWidth={strokeWidth}
          className="text-muted/20"
        />
      </svg>
    );
  }

  return (
    <svg width={size} height={size} className="-rotate-90">
      <circle
        cx={size / 2}
        cy={size / 2}
        r={radius}
        fill="none"
        stroke="currentColor"
        strokeWidth={strokeWidth}
        className="text-muted/20"
      />
      {segments.map((segment, i) => {
        const prev = i === 0 ? 0 : prefix[i - 1] ?? 0;
        const segmentCircumference = (segment.value / total) * circumference;
        const offset = circumference - (prev / total) * circumference;
        return (
          <circle
            key={i}
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke={segment.color}
            strokeWidth={strokeWidth}
            strokeLinecap="round"
            strokeDasharray={`${segmentCircumference} ${circumference - segmentCircumference}`}
            strokeDashoffset={-offset + circumference}
            className="transition-all duration-500"
          />
        );
      })}
    </svg>
  );
}
