import { useState, useEffect, useCallback, useMemo } from "react";
import { useSearchParams } from "react-router-dom";
import RiskBadge from "../../components/RiskBadge";
import { getReviewList, submitReview } from "../../services/api";
import type { ReviewItem, SuggestionItem } from "../../services/api";

type Tab = "optimization" | "pending" | "appeals" | "stats";

/* ---- Type / badge helpers (shared with SuggestPage) ---- */
const typeLabels: Record<string, string> = {
  rephrase: "改写表达",
  restructure: "调整结构",
  tone: "语气调整",
  vocabulary: "词汇优化",
  general: "综合改进",
};

const typeBadgeColors: Record<string, string> = {
  rephrase: "bg-blue-100 text-blue-700",
  restructure: "bg-purple-100 text-purple-700",
  tone: "bg-amber-100 text-amber-700",
  vocabulary: "bg-teal-100 text-teal-700",
  general: "bg-gray-100 text-gray-700",
};

export default function ReviewPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const tabParam = searchParams.get("tab");

  const [activeTab, setActiveTab] = useState<Tab>(
    tabParam === "optimization" ? "optimization" : "optimization"
  );

  // Sync tab from URL on mount / URL change
  useEffect(() => {
    if (tabParam === "optimization" || tabParam === "pending" || tabParam === "appeals" || tabParam === "stats") {
      setActiveTab(tabParam);
    }
  }, [tabParam]);

  const handleTabChange = (tab: Tab) => {
    setActiveTab(tab);
    setSearchParams({ tab });
  };

  /* ==== Optimization Results State ==== */
  const [optimizedText, setOptimizedText] = useState<string | null>(null);
  const [originalText, setOriginalText] = useState<string | null>(null);
  const [revisionLog, setRevisionLog] = useState<SuggestionItem[]>([]);
  const [revisionTimestamp, setRevisionTimestamp] = useState("");
  const [showOriginal, setShowOriginal] = useState(false);
  const [copySuccess, setCopySuccess] = useState(false);

  // Extract loader so it can be called from multiple places
  const loadOptimizationResults = useCallback(() => {
    const t = sessionStorage.getItem("sg_optimized_text");
    const o = sessionStorage.getItem("sg_original_text");
    const l = sessionStorage.getItem("sg_revision_log");
    const ts = sessionStorage.getItem("sg_revision_timestamp");

    if (t) setOptimizedText(t);
    if (o) setOriginalText(o);
    if (ts) setRevisionTimestamp(ts);
    if (l) {
      try {
        setRevisionLog(JSON.parse(l) as SuggestionItem[]);
      } catch {
        // ignore
      }
    }
  }, []);

  // Load on mount and whenever URL params change (navigating from SuggestPage)
  useEffect(() => {
    loadOptimizationResults();
  }, [searchParams, loadOptimizationResults]);

  // Also reload when switching TO the optimization tab
  useEffect(() => {
    if (activeTab === "optimization") {
      loadOptimizationResults();
    }
  }, [activeTab, loadOptimizationResults]);

  /* ---- Download helpers ---- */
  const downloadFile = useCallback((content: string, filename: string, mime: string) => {
    const blob = new Blob([content], { type: mime });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }, []);

  const handleDownloadText = useCallback(() => {
    if (!optimizedText) return;
    // Use the first non-empty line of the text as the filename
    const firstLine = optimizedText.split(/\r?\n/).find((l) => l.trim())?.trim() || "优化后文本";
    // Sanitize: remove characters invalid in filenames, truncate to 60 chars
    const safeName = firstLine.replace(/[\\/:*?"<>|]/g, "").slice(0, 60);
    downloadFile(optimizedText, `${safeName}.txt`, "text/plain;charset=utf-8");
  }, [optimizedText, downloadFile]);

  const revisionMarkdown = useMemo(() => {
    if (revisionLog.length === 0) return "";
    const lines: string[] = [
      "# 修订说明",
      "",
      `> 生成时间：${revisionTimestamp}`,
      `> 共应用 ${revisionLog.length} 条修改`,
      "",
      "---",
      "",
    ];
    revisionLog.forEach((sug, idx) => {
      lines.push(`## 修改 ${idx + 1}：${typeLabels[sug.type] ?? sug.type}`);
      lines.push("");
      lines.push(`**置信度**：${(sug.confidence * 100).toFixed(0)}%`);
      lines.push("");
      lines.push("**原文**：");
      lines.push("");
      lines.push(`> ${sug.original_text}`);
      lines.push("");
      lines.push("**修改为**：");
      lines.push("");
      lines.push(`> ${sug.suggested_text}`);
      lines.push("");
      if (sug.explanation) {
        lines.push(`**修改原因**：${sug.explanation}`);
        lines.push("");
      }
      lines.push("---");
      lines.push("");
    });
    return lines.join("\n");
  }, [revisionLog, revisionTimestamp]);

  const handleDownloadRevision = useCallback(() => {
    if (!revisionMarkdown || !optimizedText) return;
    const firstLine = optimizedText.split(/\r?\n/).find((l) => l.trim())?.trim() || "修订说明";
    const safeName = firstLine.replace(/[\\/:*?"<>|]/g, "").slice(0, 60);
    downloadFile(revisionMarkdown, `${safeName}_修订说明.md`, "text/markdown;charset=utf-8");
  }, [revisionMarkdown, optimizedText, downloadFile]);

  const handleCopyText = useCallback(() => {
    if (!optimizedText) return;
    navigator.clipboard.writeText(optimizedText).then(() => {
      setCopySuccess(true);
      setTimeout(() => setCopySuccess(false), 2000);
    });
  }, [optimizedText]);

  const hasOptimizationResults = optimizedText && revisionLog.length > 0;

  /* ==== Review Management State ==== */
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [decision, setDecision] = useState<"maintain" | "adjust" | "dismiss">(
    "maintain"
  );
  const [comment, setComment] = useState("");
  const [reviews, setReviews] = useState<ReviewItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitSuccess, setSubmitSuccess] = useState(false);

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
      loadReviews("pending");
      setSelectedId(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "提交复核决定失败");
    } finally {
      setSubmitting(false);
    }
  };

  /* ==== Tab definitions ==== */
  const tabs: { key: Tab; label: string; badge?: string }[] = [
    {
      key: "optimization",
      label: "优化结果",
      badge: hasOptimizationResults ? `${revisionLog.length}` : undefined,
    },
    { key: "pending", label: "待复核" },
    { key: "appeals", label: "申诉处理" },
    { key: "stats", label: "反馈统计" },
  ];

  return (
    <div className={`${showOriginal ? "max-w-7xl" : "max-w-5xl"} mx-auto px-6 py-8 space-y-6 transition-all`}>
      <div>
        <h2 className="text-xl font-bold text-gray-900 tracking-tight">复核中心</h2>
        <p className="text-[13px] text-gray-400 mt-1">
          审阅优化结果、管理检测复核与用户反馈
        </p>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-gray-200">
        {tabs.map((t) => (
          <button
            key={t.key}
            className={`tab ${activeTab === t.key ? "active" : ""}`}
            onClick={() => handleTabChange(t.key)}
          >
            {t.label}
            {t.badge && (
              <span className="ml-1.5 inline-flex items-center justify-center w-5 h-5 text-xs font-bold rounded-full bg-brand-100 text-brand-700">
                {t.badge}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Error */}
      {error && (
        <div className="bg-red-50 border border-red-100 text-red-600 px-5 py-3.5 rounded-2xl text-sm">
          {error}
        </div>
      )}

      {/* Success */}
      {submitSuccess && (
        <div className="bg-green-50 border border-green-100 text-green-700 px-5 py-3.5 rounded-2xl text-sm">
          复核决定已提交
        </div>
      )}

      {/* ============ Optimization Results Tab ============ */}
      {activeTab === "optimization" && (
        <>
          {hasOptimizationResults ? (
            <div className="space-y-6">
              {/* Status bar + download buttons */}
              <div className="card">
                <div className="flex items-center justify-between flex-wrap gap-3">
                  <div className="flex items-center gap-2">
                    <span className="w-8 h-8 rounded-full bg-green-100 flex items-center justify-center text-green-600 text-lg">
                      ✓
                    </span>
                    <div>
                      <p className="text-sm font-bold text-gray-700">
                        优化已完成
                      </p>
                      <p className="text-xs text-gray-500">
                        共应用 {revisionLog.length} 条修改 · {revisionTimestamp}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      className="btn-primary text-sm"
                      onClick={handleDownloadText}
                    >
                      下载优化后文本
                    </button>
                    <button
                      type="button"
                      className="btn-secondary text-sm"
                      onClick={handleDownloadRevision}
                    >
                      下载修订说明
                    </button>
                  </div>
                </div>
              </div>

              {/* Optimized text display (side-by-side when comparing) */}
              <div className="card space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <h3 className="text-sm font-bold text-gray-700">
                      优化后文本
                    </h3>
                    {!showOriginal && (
                      <button
                        type="button"
                        className="text-xs text-brand-600 hover:text-brand-700 font-medium border border-brand-200 rounded-full px-3 py-0.5"
                        onClick={() => setShowOriginal(true)}
                      >
                        对比全文
                      </button>
                    )}
                  </div>
                  <button
                    type="button"
                    className="text-xs text-brand-600 hover:text-brand-700 font-medium"
                    onClick={handleCopyText}
                  >
                    {copySuccess ? "已复制 ✓" : "复制全文"}
                  </button>
                </div>

                <div className={`grid gap-4 ${showOriginal ? "grid-cols-2" : "grid-cols-1"}`}>
                  {/* Left: optimized text */}
                  <div>
                    {showOriginal && (
                      <p className="text-xs font-medium text-green-600 mb-1.5">优化后文本</p>
                    )}
                    <div className="text-sm text-gray-800 leading-relaxed bg-gray-50 rounded-2xl p-4 whitespace-pre-wrap max-h-[400px] overflow-y-auto">
                      {optimizedText}
                    </div>
                  </div>

                  {/* Right: original text (closeable) */}
                  {showOriginal && (
                    <div>
                      <div className="flex items-center justify-between mb-1.5">
                        <p className="text-xs font-medium text-gray-500">原始文本</p>
                        <button
                          type="button"
                          className="text-xs text-gray-400 hover:text-gray-600"
                          onClick={() => setShowOriginal(false)}
                          title="关闭对比"
                        >
                          ✕ 关闭
                        </button>
                      </div>
                      <div className="text-sm text-gray-600 leading-relaxed bg-gray-50 rounded-2xl p-4 whitespace-pre-wrap max-h-[400px] overflow-y-auto border border-gray-200">
                        {originalText}
                      </div>
                    </div>
                  )}
                </div>
              </div>

              {/* Revision log */}
              <div className="card space-y-3">
                <h3 className="text-sm font-bold text-gray-700">
                  修订说明
                  <span className="text-sm font-normal text-gray-400 ml-2">
                    {revisionLog.length} 条修改
                  </span>
                </h3>
                <div className="space-y-3 max-h-[600px] overflow-y-auto">
                  {revisionLog.map((sug, idx) => (
                    <div
                      key={sug.suggestion_id}
                      className="border border-gray-200 rounded-2xl overflow-hidden"
                    >
                      {/* Header */}
                      <div className="flex items-center gap-2 px-4 py-2 bg-gray-50 border-b border-gray-100">
                        <span className="text-xs font-bold text-gray-500">
                          #{idx + 1}
                        </span>
                        <span
                          className={`text-xs font-medium px-2 py-0.5 rounded-full ${
                            typeBadgeColors[sug.type] ?? "bg-gray-100 text-gray-700"
                          }`}
                        >
                          {typeLabels[sug.type] ?? sug.type}
                        </span>
                        <span className="text-xs text-gray-400">
                          置信度 {(sug.confidence * 100).toFixed(0)}%
                        </span>
                      </div>
                      {/* Body */}
                      <div className="p-4 space-y-2">
                        <div className="grid grid-cols-2 gap-3">
                          <div>
                            <span className="text-xs text-gray-400">原文</span>
                            <p className="text-sm text-gray-600 bg-red-50 rounded px-3 py-2 mt-1 line-through">
                              {sug.original_text}
                            </p>
                          </div>
                          <div>
                            <span className="text-xs text-gray-400">修改为</span>
                            <p className="text-sm text-gray-900 bg-green-50 rounded px-3 py-2 mt-1">
                              {sug.suggested_text}
                            </p>
                          </div>
                        </div>
                        {sug.explanation && (
                          <p className="text-xs text-gray-500 italic">
                            修改原因：{sug.explanation}
                          </p>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            <div className="card text-center py-16">
              <div className="text-4xl mb-3">📝</div>
              <p className="text-lg text-gray-500 mb-1">暂无优化结果</p>
              <p className="text-sm text-gray-400">
                请先在「写作建议」页面完成检测问题审核并执行一键优化
              </p>
            </div>
          )}
        </>
      )}

      {/* ============ Pending Reviews Tab ============ */}
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
                className={`w-full text-left p-3 rounded-2xl border transition-colors ${
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
                <div className="flex items-center gap-2 mt-1">
                  <p className="text-xs text-gray-400">
                    {item.detection_id}
                  </p>
                  {item.optimization_data && (
                    <span className="text-xs text-green-600 font-medium bg-green-50 px-1.5 py-0.5 rounded">
                      ✓ 已优化
                    </span>
                  )}
                </div>
              </button>
            ))}
          </div>

          {/* Detail / Review form */}
          <div className="col-span-3">
            {selected ? (
              <div className="card space-y-4">
                <div className="flex items-center justify-between">
                  <h4 className="text-sm font-bold text-gray-700">复核详情</h4>
                  <RiskBadge
                    level={selected.risk_level}
                    score={selected.risk_score}
                  />
                </div>
                <p className="text-sm text-gray-600 leading-relaxed bg-gray-50 rounded-2xl p-4">
                  {selected.text_preview}
                </p>

                {/* Optimization results (if available) */}
                {selected.optimization_data && (
                  <div className="border border-green-200 bg-green-50/30 rounded-2xl p-4 space-y-3">
                    <div className="flex items-center gap-2">
                      <span className="w-5 h-5 rounded-full bg-green-100 flex items-center justify-center text-green-600 text-xs font-bold">✓</span>
                      <h5 className="text-sm font-bold text-gray-700">优化结果</h5>
                      <span className="text-xs text-gray-400">
                        {selected.optimization_data.suggestions.length} 条修改
                      </span>
                    </div>

                    {/* Optimized text preview */}
                    <div>
                      <span className="label">优化后文本</span>
                      <p className="text-sm text-gray-700 bg-white border border-green-100 rounded-2xl p-3 mt-1 max-h-[160px] overflow-y-auto whitespace-pre-wrap leading-relaxed">
                        {selected.optimization_data.optimized_text.slice(0, 500)}
                        {selected.optimization_data.optimized_text.length > 500 && "..."}
                      </p>
                    </div>

                    {/* Revision log */}
                    <div>
                      <span className="label">修改明细</span>
                      <div className="space-y-2 mt-1 max-h-[300px] overflow-y-auto">
                        {selected.optimization_data.suggestions.map((sug, idx) => (
                          <div key={sug.suggestion_id || idx} className="bg-white border border-gray-100 rounded p-3">
                            <div className="flex items-center gap-2 mb-1.5">
                              <span className="text-xs font-bold text-gray-400">#{idx + 1}</span>
                              <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${
                                sug.type === "rephrase" ? "bg-blue-100 text-blue-700" :
                                sug.type === "restructure" ? "bg-purple-100 text-purple-700" :
                                sug.type === "tone" ? "bg-amber-100 text-amber-700" :
                                sug.type === "vocabulary" ? "bg-teal-100 text-teal-700" :
                                "bg-gray-100 text-gray-700"
                              }`}>
                                {typeLabels[sug.type] ?? sug.type}
                              </span>
                              <span className="text-xs text-gray-400">
                                置信度 {(sug.confidence * 100).toFixed(0)}%
                              </span>
                            </div>
                            <div className="grid grid-cols-2 gap-2">
                              <div>
                                <span className="text-xs text-gray-400">原文</span>
                                <p className="text-xs text-gray-500 bg-red-50 rounded px-2 py-1 mt-0.5 line-through">{sug.original_text}</p>
                              </div>
                              <div>
                                <span className="text-xs text-gray-400">修改为</span>
                                <p className="text-xs text-gray-800 bg-green-50 rounded px-2 py-1 mt-0.5">{sug.suggested_text}</p>
                              </div>
                            </div>
                            {sug.explanation && (
                              <p className="text-xs text-gray-500 italic mt-1.5">原因：{sug.explanation}</p>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                )}

                <div className="border-t border-gray-100 pt-4 space-y-3">
                  <p className="text-sm font-bold text-gray-700">复核决定</p>
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

      {/* ============ Appeals Tab ============ */}
      {activeTab === "appeals" && (
        <div className="card text-center py-16 text-gray-400">
          <p className="text-lg mb-1">申诉处理</p>
          <p className="text-sm">暂无待处理申诉</p>
        </div>
      )}

      {/* ============ Stats Tab ============ */}
      {activeTab === "stats" && (
        <div className="card space-y-4">
          <h4 className="text-sm font-bold text-gray-700">反馈统计概览</h4>
          <div className="grid grid-cols-4 gap-4">
            {[
              { label: "总反馈数", value: "128" },
              { label: "认同率", value: "73%" },
              { label: "待处理复核", value: "3" },
              { label: "本月申诉", value: "5" },
            ].map((stat) => (
              <div
                key={stat.label}
                className="bg-gray-50 rounded-2xl p-4 text-center"
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
