import { useState, useEffect, useCallback } from "react";
import RiskBadge from "../../components/RiskBadge";
import { getReviewList, submitReview } from "../../services/api";
import type { ReviewItem } from "../../services/api";

type Tab = "pending" | "appeals" | "stats";

export default function ReviewPage() {
  const [activeTab, setActiveTab] = useState<Tab>("pending");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [decision, setDecision] = useState<"maintain" | "adjust" | "dismiss">(
    "maintain"
  );
  const [comment, setComment] = useState("");

  /* ---- Data state ---- */
  const [reviews, setReviews] = useState<ReviewItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitSuccess, setSubmitSuccess] = useState(false);

  const tabs: { key: Tab; label: string }[] = [
    { key: "pending", label: "待复核" },
    { key: "appeals", label: "申诉处理" },
    { key: "stats", label: "反馈统计" },
  ];

  /* ---- Load reviews ---- */
  const loadReviews = useCallback(async (status?: string) => {
    setLoading(true);
    setError("");
    try {
      const result = await getReviewList(status);
      setReviews(result.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载复核列表失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (activeTab === "pending") {
      loadReviews("pending");
    }
  }, [activeTab, loadReviews]);

  const selected = reviews.find((r) => r.id === selectedId);

  /* ---- Submit review decision ---- */
  const handleSubmitReview = async () => {
    if (!selectedId) return;
    setSubmitting(true);
    setSubmitSuccess(false);
    try {
      await submitReview(selectedId, decision, comment);
      setSubmitSuccess(true);
      setComment("");
      // Reload the list to reflect status change
      loadReviews("pending");
      setSelectedId(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "提交复核决定失败");
    } finally {
      setSubmitting(false);
    }
  };

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

      {/* Error */}
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm">
          {error}
        </div>
      )}

      {/* Success */}
      {submitSuccess && (
        <div className="bg-green-50 border border-green-200 text-green-700 px-4 py-3 rounded-lg text-sm">
          复核决定已提交
        </div>
      )}

      {/* Pending reviews */}
      {activeTab === "pending" && (
        <div className="grid grid-cols-5 gap-6">
          {/* List */}
          <div className="col-span-2 space-y-2">
            {loading && (
              <p className="text-sm text-gray-500 py-4">加载中...</p>
            )}
            {!loading && reviews.length === 0 && (
              <p className="text-sm text-gray-400 py-4">暂无待复核项</p>
            )}
            {reviews.map((item) => (
              <button
                key={item.id}
                className={`w-full text-left p-3 rounded-lg border transition-colors ${
                  selectedId === item.id
                    ? "border-brand-500 bg-brand-50"
                    : "border-gray-200 hover:border-gray-300"
                }`}
                onClick={() => {
                  setSelectedId(item.id);
                  setSubmitSuccess(false);
                }}
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs text-gray-400">
                    {item.submitted_at}
                  </span>
                  <RiskBadge
                    level={item.risk_level}
                    score={item.risk_score}
                    size="sm"
                  />
                </div>
                <p className="text-sm text-gray-700 truncate">
                  {item.text_preview}
                </p>
                <p className="text-xs text-gray-400 mt-1">
                  {item.detection_id}
                </p>
              </button>
            ))}
          </div>

          {/* Detail / Review form */}
          <div className="col-span-3">
            {selected ? (
              <div className="card space-y-4">
                <div className="flex items-center justify-between">
                  <h4 className="font-semibold text-gray-900">复核详情</h4>
                  <RiskBadge
                    level={selected.risk_level}
                    score={selected.risk_score}
                  />
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
                      <label
                        key={val}
                        className="flex items-center gap-1.5 text-sm"
                      >
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
                  <button
                    className="btn-primary"
                    disabled={submitting}
                    onClick={handleSubmitReview}
                  >
                    {submitting ? "提交中..." : "提交复核"}
                  </button>
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
              <div
                key={stat.label}
                className="bg-gray-50 rounded-lg p-4 text-center"
              >
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
