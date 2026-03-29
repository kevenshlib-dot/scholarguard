import { useState } from "react";
import RiskBadge from "../../components/RiskBadge";

type Tab = "pending" | "appeals" | "stats";

interface ReviewItem {
  id: string;
  detection_id: string;
  submitted_at: string;
  risk_level: string;
  risk_score: number;
  text_preview: string;
  status: string;
}

const mockPending: ReviewItem[] = [
  {
    id: "rev-001",
    detection_id: "det-003",
    submitted_at: "2026-03-29 08:12",
    risk_level: "high",
    risk_score: 0.78,
    text_preview: "The impact of artificial intelligence on modern governance structures...",
    status: "pending",
  },
  {
    id: "rev-002",
    detection_id: "det-005",
    submitted_at: "2026-03-28 15:30",
    risk_level: "medium",
    risk_score: 0.48,
    text_preview: "在经济全球化的大背景下，数字货币的发展引发了...",
    status: "pending",
  },
  {
    id: "rev-003",
    detection_id: "det-007",
    submitted_at: "2026-03-27 11:00",
    risk_level: "critical",
    risk_score: 0.92,
    text_preview: "本文通过大规模语言模型的系统分析，探讨了人工智能在...",
    status: "pending",
  },
];

export default function ReviewPage() {
  const [activeTab, setActiveTab] = useState<Tab>("pending");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [decision, setDecision] = useState<"maintain" | "adjust" | "dismiss">("maintain");
  const [comment, setComment] = useState("");

  const tabs: { key: Tab; label: string }[] = [
    { key: "pending", label: "待复核" },
    { key: "appeals", label: "申诉处理" },
    { key: "stats", label: "反馈统计" },
  ];

  const selected = mockPending.find((r) => r.id === selectedId);

  return (
    <div className="max-w-5xl mx-auto px-6 py-8 space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-gray-900">复核中心</h2>
        <p className="text-sm text-gray-500 mt-1">
          管理检测复核请求和用户反馈
        </p>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-gray-200">
        {tabs.map((t) => (
          <button
            key={t.key}
            className={`tab ${activeTab === t.key ? "active" : ""}`}
            onClick={() => setActiveTab(t.key)}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Pending reviews */}
      {activeTab === "pending" && (
        <div className="grid grid-cols-5 gap-6">
          {/* List */}
          <div className="col-span-2 space-y-2">
            {mockPending.map((item) => (
              <button
                key={item.id}
                className={`w-full text-left p-3 rounded-lg border transition-colors ${
                  selectedId === item.id
                    ? "border-brand-500 bg-brand-50"
                    : "border-gray-200 hover:border-gray-300"
                }`}
                onClick={() => setSelectedId(item.id)}
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs text-gray-400">{item.submitted_at}</span>
                  <RiskBadge level={item.risk_level} score={item.risk_score} size="sm" />
                </div>
                <p className="text-sm text-gray-700 truncate">{item.text_preview}</p>
                <p className="text-xs text-gray-400 mt-1">{item.detection_id}</p>
              </button>
            ))}
          </div>

          {/* Detail / Review form */}
          <div className="col-span-3">
            {selected ? (
              <div className="card space-y-4">
                <div className="flex items-center justify-between">
                  <h4 className="font-semibold text-gray-900">复核详情</h4>
                  <RiskBadge level={selected.risk_level} score={selected.risk_score} />
                </div>
                <p className="text-sm text-gray-600 leading-relaxed bg-gray-50 rounded-lg p-4">
                  {selected.text_preview}
                </p>

                <div className="border-t border-gray-100 pt-4 space-y-3">
                  <p className="text-sm font-medium text-gray-700">复核决定</p>
                  <div className="flex gap-3">
                    {(
                      [
                        ["maintain", "维持判定"],
                        ["adjust", "调整等级"],
                        ["dismiss", "撤销判定"],
                      ] as const
                    ).map(([val, label]) => (
                      <label key={val} className="flex items-center gap-1.5 text-sm">
                        <input
                          type="radio"
                          name="decision"
                          value={val}
                          checked={decision === val}
                          onChange={() => setDecision(val)}
                          className="accent-brand-600"
                        />
                        {label}
                      </label>
                    ))}
                  </div>
                  <textarea
                    className="input min-h-[80px]"
                    placeholder="复核意见..."
                    value={comment}
                    onChange={(e) => setComment(e.target.value)}
                  />
                  <button className="btn-primary">提交复核</button>
                </div>
              </div>
            ) : (
              <div className="card flex items-center justify-center h-64 text-gray-400 text-sm">
                请选择左侧待复核项
              </div>
            )}
          </div>
        </div>
      )}

      {/* Appeals tab */}
      {activeTab === "appeals" && (
        <div className="card text-center py-16 text-gray-400">
          <p className="text-lg mb-1">申诉处理</p>
          <p className="text-sm">暂无待处理申诉</p>
        </div>
      )}

      {/* Stats tab */}
      {activeTab === "stats" && (
        <div className="card space-y-4">
          <h4 className="font-semibold text-gray-900">反馈统计概览</h4>
          <div className="grid grid-cols-4 gap-4">
            {[
              { label: "总反馈数", value: "128" },
              { label: "认同率", value: "73%" },
              { label: "待处理复核", value: "3" },
              { label: "本月申诉", value: "5" },
            ].map((stat) => (
              <div key={stat.label} className="bg-gray-50 rounded-lg p-4 text-center">
                <p className="text-2xl font-bold text-gray-900">{stat.value}</p>
                <p className="text-xs text-gray-500 mt-1">{stat.label}</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
