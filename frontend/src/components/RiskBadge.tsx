interface RiskBadgeProps {
  level: string;
  score?: number;
  size?: "sm" | "md" | "lg";
}

const config: Record<
  string,
  { bg: string; text: string; ring: string; dot: string; label: string }
> = {
  low: {
    bg: "bg-emerald-50",
    text: "text-emerald-700",
    ring: "ring-emerald-200",
    dot: "bg-emerald-500",
    label: "低风险",
  },
  medium: {
    bg: "bg-amber-50",
    text: "text-amber-700",
    ring: "ring-amber-200",
    dot: "bg-amber-500",
    label: "中风险",
  },
  high: {
    bg: "bg-red-50",
    text: "text-red-700",
    ring: "ring-red-200",
    dot: "bg-red-500",
    label: "高风险",
  },
  critical: {
    bg: "bg-purple-50",
    text: "text-purple-700",
    ring: "ring-purple-200",
    dot: "bg-purple-500",
    label: "极高风险",
  },
  unknown: {
    bg: "bg-gray-100",
    text: "text-gray-500",
    ring: "ring-gray-200",
    dot: "bg-gray-400",
    label: "检测失败",
  },
  error: {
    bg: "bg-gray-100",
    text: "text-gray-500",
    ring: "ring-gray-200",
    dot: "bg-gray-400",
    label: "检测失败",
  },
};

const sizeClasses: Record<string, { badge: string; dot: string }> = {
  sm: { badge: "px-2.5 py-0.5 text-[11px]", dot: "w-1.5 h-1.5" },
  md: { badge: "px-3 py-1 text-xs", dot: "w-2 h-2" },
  lg: { badge: "px-4 py-1.5 text-sm", dot: "w-2 h-2" },
};

export default function RiskBadge({
  level,
  score,
  size = "md",
}: RiskBadgeProps) {
  const c = config[level] ?? config.low;
  const s = sizeClasses[size] ?? sizeClasses.md;
  return (
    <span
      className={`inline-flex items-center gap-1.5 font-bold rounded-full ring-1 ${c.bg} ${c.text} ${c.ring} ${s.badge}`}
    >
      <span className={`${s.dot} rounded-full ${c.dot}`} />
      <span>{c.label}</span>
      {score !== undefined && (
        <span className="opacity-60 font-semibold">
          {(score * 100).toFixed(0)}%
        </span>
      )}
    </span>
  );
}
