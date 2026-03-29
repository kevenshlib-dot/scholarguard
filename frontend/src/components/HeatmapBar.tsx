import { useState } from "react";

interface HeatmapBarProps {
  paragraphs: { index: number; text: string; score: number; risk_level: string }[];
}

function scoreToColor(score: number): string {
  if (score < 0.3) return "bg-green-400";
  if (score < 0.5) return "bg-yellow-400";
  if (score < 0.7) return "bg-orange-400";
  if (score < 0.85) return "bg-red-400";
  return "bg-purple-500";
}

function scoreToLabel(score: number): string {
  if (score < 0.3) return "低";
  if (score < 0.5) return "中";
  if (score < 0.7) return "偏高";
  if (score < 0.85) return "高";
  return "极高";
}

export default function HeatmapBar({ paragraphs }: HeatmapBarProps) {
  const [hoveredIdx, setHoveredIdx] = useState<number | null>(null);

  if (!paragraphs || paragraphs.length === 0) return null;

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 text-xs text-gray-500">
        <span>段落风险热力图</span>
        <div className="flex items-center gap-1 ml-auto">
          <span className="w-3 h-3 rounded-sm bg-green-400" /> 低
          <span className="w-3 h-3 rounded-sm bg-yellow-400 ml-2" /> 中
          <span className="w-3 h-3 rounded-sm bg-orange-400 ml-2" /> 偏高
          <span className="w-3 h-3 rounded-sm bg-red-400 ml-2" /> 高
          <span className="w-3 h-3 rounded-sm bg-purple-500 ml-2" /> 极高
        </div>
      </div>

      {/* Bar blocks */}
      <div className="flex gap-1">
        {paragraphs.map((p) => (
          <div
            key={p.index}
            className={`relative flex-1 h-10 rounded cursor-pointer transition-all ${scoreToColor(p.score)} ${
              hoveredIdx === p.index
                ? "ring-2 ring-brand-600 ring-offset-1 scale-105"
                : "hover:opacity-80"
            }`}
            onMouseEnter={() => setHoveredIdx(p.index)}
            onMouseLeave={() => setHoveredIdx(null)}
            title={`段落${p.index + 1}: ${scoreToLabel(p.score)} (${(p.score * 100).toFixed(0)}%)`}
          >
            <span className="absolute inset-0 flex items-center justify-center text-white text-[10px] font-bold">
              {p.index + 1}
            </span>
          </div>
        ))}
      </div>

      {/* Tooltip detail */}
      {hoveredIdx !== null && paragraphs[hoveredIdx] && (
        <div className="bg-gray-800 text-white text-xs rounded-lg p-3 animate-in fade-in">
          <div className="flex items-center gap-2 mb-1.5">
            <span className="font-semibold">段落 {hoveredIdx + 1}</span>
            <span
              className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${scoreToColor(paragraphs[hoveredIdx].score)} text-white`}
            >
              {scoreToLabel(paragraphs[hoveredIdx].score)}{" "}
              {(paragraphs[hoveredIdx].score * 100).toFixed(0)}%
            </span>
          </div>
          <p className="text-gray-300 line-clamp-3 leading-relaxed">
            {paragraphs[hoveredIdx].text}
          </p>
        </div>
      )}
    </div>
  );
}
