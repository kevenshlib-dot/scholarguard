import { useState } from "react";
import { Link } from "react-router-dom";
import RiskBadge from "../../components/RiskBadge";

interface HistoryItem {
  id: string;
  created_at: string;
  text_preview: string;
  risk_level: string;
  risk_score: number;
  status: string;
}

// Mock data for display; replace with real API call
const mockHistory: HistoryItem[] = [
  {
    id: "det-001",
    created_at: "2026-03-29 10:23",
    text_preview: "本研究采用混合方法，对长三角地区的...",
    risk_level: "low",
    risk_score: 0.15,
    status: "completed",
  },
  {
    id: "det-002",
    created_at: "2026-03-28 16:45",
    text_preview: "在全球化背景下，国际贸易格局发生了深刻变化...",
    risk_level: "medium",
    risk_score: 0.52,
    status: "completed",
  },
  {
    id: "det-003",
    created_at: "2026-03-27 09:12",
    text_preview: "The impact of artificial intelligence on modern governance...",
    risk_level: "high",
    risk_score: 0.78,
    status: "completed",
  },
];

export default function HistoryPage() {
  const [items] = useState<HistoryItem[]>(mockHistory);

  return (
    <div className="max-w-4xl mx-auto px-6 py-8 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">检测历史</h2>
          <p className="text-sm text-gray-500 mt-1">查看过往检测记录</p>
        </div>
        <Link to="/detect" className="btn-primary">
          新建检测
        </Link>
      </div>

      <div className="card divide-y divide-gray-100">
        {items.length === 0 ? (
          <p className="text-center text-gray-400 py-12">暂无检测记录</p>
        ) : (
          items.map((item) => (
            <div
              key={item.id}
              className="flex items-center gap-4 py-4 first:pt-0 last:pb-0"
            >
              <div className="flex-1 min-w-0">
                <p className="text-sm text-gray-900 truncate">
                  {item.text_preview}
                </p>
                <p className="text-xs text-gray-400 mt-0.5">
                  {item.created_at} &middot; {item.id}
                </p>
              </div>
              <RiskBadge
                level={item.risk_level}
                score={item.risk_score}
                size="sm"
              />
            </div>
          ))
        )}
      </div>
    </div>
  );
}
