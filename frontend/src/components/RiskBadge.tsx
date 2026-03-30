interface RiskBadgeProps {
  level: string;
  score?: number;
  size?: "sm" | "md" | "lg";
}

const config: Record<string, { bg: string; text: string; label: string }> = {
  low: { bg: "bg-green-100", text: "text-green-700", label: "低风险" },
  medium: { bg: "bg-yellow-100", text: "text-yellow-700", label: "中风险" },
  high: { bg: "bg-red-100", text: "text-red-700", label: "高风险" },
  critical: {
    bg: "bg-purple-100",
    text: "text-purple-700",
    label: "极高风险",
  },
  unknown: {
    bg: "bg-gray-100",
    text: "text-gray-500",
    label: "检测失败",
  },
  error: {
    bg: "bg-gray-100",
    text: "text-gray-500",
    label: "检测失败",
  },
};

const sizeClasses: Record<string, string> = {
  sm: "px-2 py-0.5 text-xs",
  md: "px-3 py-1 text-sm",
  lg: "px-4 py-1.5 text-base",
};

export default function RiskBadge({
  level,
  score,
  size = "md",
}: RiskBadgeProps) {
  const c = config[level] ?? config.low;
  return (
    <span
      className={`inline-flex items-center gap-1.5 font-semibold rounded-full ${c.bg} ${c.text} ${sizeClasses[size]}`}
    >
      <span>{c.label}</span>
      {score !== undefined && (
        <span className="opacity-70">({(score * 100).toFixed(0)}%)</span>
      )}
    </span>
  );
}
