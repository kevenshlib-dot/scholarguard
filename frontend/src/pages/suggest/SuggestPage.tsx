import { useState, useCallback, useMemo } from "react";
import { getSuggestions } from "../../services/api";
import type { SuggestionItem, DetectResultData } from "../../services/api";

/* ---- Strategy definitions ---- */
const strategies = [
  { value: "rephrase", label: "改写表达", desc: "使文本更贴近人类自然写作风格" },
  { value: "restructure", label: "调整结构", desc: "优化段落组织和逻辑层次" },
  { value: "vocabulary", label: "词汇优化", desc: "丰富用词，减少AI常见表达" },
  { value: "tone", label: "语气调整", desc: "调整文本语气使其更自然" },
  { value: "general", label: "综合改进", desc: "全方位改进文本质量" },
];

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

/* ---- Auto-select logic ---- */
function autoSelectStrategies(detectResult: DetectResultData): string[] {
  const selected = new Set<string>();
  const segments = detectResult.flagged_segments ?? [];
  for (const seg of segments) {
    const issue = (seg.issue ?? "").toLowerCase();
    if (issue.includes("结构") || issue.includes("逻辑")) selected.add("restructure");
    if (issue.includes("表达") || issue.includes("自然") || issue.includes("生硬")) selected.add("rephrase");
    if (issue.includes("词汇") || issue.includes("用词")) selected.add("vocabulary");
    if (issue.includes("语气") || issue.includes("tone")) selected.add("tone");
  }
  if (selected.size === 0) {
    selected.add("rephrase");
    selected.add("vocabulary");
  }
  return Array.from(selected);
}

/* ---- Risk level label ---- */
function riskLevelLabel(level: string): { text: string; className: string } {
  switch (level) {
    case "critical":
      return { text: "极高风险", className: "bg-red-200 text-red-800" };
    case "high":
      return { text: "高风险", className: "bg-red-100 text-red-700" };
    case "medium":
      return { text: "中风险", className: "bg-amber-100 text-amber-700" };
    case "low":
      return { text: "低风险", className: "bg-green-100 text-green-700" };
    default:
      return { text: level, className: "bg-gray-100 text-gray-700" };
  }
}

export default function SuggestPage() {
  /* ---- State ---- */
  const [text, setText] = useState("");
  const [selected, setSelected] = useState<string[]>(["rephrase", "vocabulary"]);
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<SuggestionItem[]>([]);
  const [originalRiskScore, setOriginalRiskScore] = useState<number | null>(null);
  const [estimatedRiskScore, setEstimatedRiskScore] = useState<number | null>(null);
  const [error, setError] = useState("");

  // Detection context (imported from DetectPage)
  const [detectResult, setDetectResult] = useState<DetectResultData | null>(null);

  // Accept/reject state per suggestion
  const [accepted, setAccepted] = useState<Record<string, boolean>>({});

  // Undo history
  const [textHistory, setTextHistory] = useState<string[]>([]);

  /* ---- Helpers ---- */
  const toggle = (val: string) => {
    setSelected((prev) =>
      prev.includes(val) ? prev.filter((v) => v !== val) : [...prev, val]
    );
  };

  /* ---- Import from detection ---- */
  const handleImport = useCallback(() => {
    const storedText = sessionStorage.getItem("sg_detect_text");
    const storedResult = sessionStorage.getItem("sg_detect_result");

    if (!storedText && !storedResult) {
      setError("没有找到检测结果，请先在检测页面完成检测。");
      return;
    }

    if (storedText) {
      setText(storedText);
    }

    if (storedResult) {
      try {
        const parsed = JSON.parse(storedResult) as DetectResultData;
        setDetectResult(parsed);
        const autoStrategies = autoSelectStrategies(parsed);
        setSelected(autoStrategies);
      } catch {
        // Ignore parse errors
      }
    }

    setResults([]);
    setAccepted({});
    setError("");
  }, []);

  /* ---- Submit for suggestions ---- */
  const handleSubmit = async () => {
    if (!text.trim() || selected.length === 0) return;
    setLoading(true);
    setError("");
    setResults([]);
    setAccepted({});
    try {
      const res = await getSuggestions(
        text,
        selected,
        detectResult?.task_id,
        undefined,
        undefined
      );
      setResults(res.suggestions);
      setOriginalRiskScore(res.original_risk_score);
      setEstimatedRiskScore(res.estimated_risk_score);
      // Initialize all as neither accepted nor rejected
      const initial: Record<string, boolean> = {};
      for (const s of res.suggestions) {
        initial[s.suggestion_id] = false;
      }
      setAccepted(initial);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "请求失败");
    } finally {
      setLoading(false);
    }
  };

  /* ---- Accept / Reject ---- */
  const handleAccept = (id: string) => {
    setAccepted((prev) => ({ ...prev, [id]: true }));
  };

  const handleReject = (id: string) => {
    setAccepted((prev) => ({ ...prev, [id]: false }));
  };

  const handleAcceptAll = () => {
    setAccepted((prev) => {
      const next = { ...prev };
      for (const key of Object.keys(next)) {
        next[key] = true;
      }
      return next;
    });
  };

  /* ---- Apply accepted suggestions ---- */
  const acceptedSuggestions = useMemo(
    () => results.filter((s) => accepted[s.suggestion_id]),
    [results, accepted]
  );

  const acceptedCount = acceptedSuggestions.length;

  const handleApply = useCallback(() => {
    if (acceptedCount === 0) return;

    // Push current text to history for undo
    setTextHistory((prev) => [...prev, text]);

    // Sort accepted suggestions by offset descending so replacements don't shift offsets
    const sorted = [...acceptedSuggestions].sort(
      (a, b) => b.offset_start - a.offset_start
    );

    let newText = text;
    for (const s of sorted) {
      const before = newText.slice(0, s.offset_start);
      const after = newText.slice(s.offset_end);
      newText = before + s.suggested_text + after;
    }

    setText(newText);
    setResults([]);
    setAccepted({});
  }, [text, acceptedSuggestions, acceptedCount]);

  /* ---- Undo ---- */
  const handleUndo = useCallback(() => {
    if (textHistory.length === 0) return;
    const prev = textHistory[textHistory.length - 1];
    setTextHistory((h) => h.slice(0, -1));
    setText(prev);
    setResults([]);
    setAccepted({});
  }, [textHistory]);

  /* ---- Preview text with applied suggestions ---- */
  const previewHtml = useMemo(() => {
    if (acceptedCount === 0) return null;

    const sorted = [...acceptedSuggestions].sort(
      (a, b) => a.offset_start - b.offset_start
    );

    const parts: string[] = [];
    let lastEnd = 0;

    for (const s of sorted) {
      // Text before this suggestion
      if (s.offset_start > lastEnd) {
        parts.push(escapeHtml(text.slice(lastEnd, s.offset_start)));
      }
      // The replaced text highlighted
      parts.push(
        `<span class="bg-green-200 text-green-900 px-0.5 rounded">${escapeHtml(s.suggested_text)}</span>`
      );
      lastEnd = s.offset_end;
    }

    // Remaining text
    if (lastEnd < text.length) {
      parts.push(escapeHtml(text.slice(lastEnd)));
    }

    return parts.join("");
  }, [text, acceptedSuggestions, acceptedCount]);

  return (
    <div className="max-w-4xl mx-auto px-6 py-8 space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold text-gray-900">写作建议</h2>
        <p className="text-sm text-gray-500 mt-1">
          获取改善文本自然度和学术质量的建议，支持从检测结果一键导入
        </p>
      </div>

      {/* Input Card */}
      <div className="card space-y-4">
        {/* Text area with import button */}
        <div>
          <div className="flex items-center justify-between mb-1.5">
            <label className="block text-sm font-medium text-gray-700">
              输入文本
            </label>
            <button
              type="button"
              className="text-sm text-brand-600 hover:text-brand-700 font-medium"
              onClick={handleImport}
            >
              从检测结果导入
            </button>
          </div>
          <textarea
            className="input min-h-[200px] resize-y"
            placeholder="粘贴您的学术文本，或点击右上角「从检测结果导入」..."
            value={text}
            onChange={(e) => setText(e.target.value)}
          />
          <div className="flex items-center justify-between mt-2">
            <p className="text-xs text-gray-400">{text.length} 字符</p>
            {text.length > 0 && (
              <button
                type="button"
                className="text-xs text-red-500 hover:text-red-600 font-medium"
                onClick={() => {
                  setText("");
                  setResults([]);
                  setAccepted({});
                  setDetectResult(null);
                  setError("");
                }}
              >
                清空文本
              </button>
            )}
          </div>
        </div>

        {/* Detection context banner */}
        {detectResult && (
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
            <div className="flex items-center gap-3 flex-wrap">
              <span className="text-sm font-medium text-blue-800">
                已导入检测结果
              </span>
              {detectResult.risk_level && (
                <span
                  className={`text-xs font-medium px-2 py-0.5 rounded-full ${
                    riskLevelLabel(detectResult.risk_level).className
                  }`}
                >
                  {riskLevelLabel(detectResult.risk_level).text}
                </span>
              )}
              {detectResult.risk_score !== undefined && (
                <span className="text-xs text-blue-700">
                  风险分数：{(detectResult.risk_score * 100).toFixed(1)}%
                </span>
              )}
              {detectResult.flagged_segments && (
                <span className="text-xs text-blue-700">
                  发现 {detectResult.flagged_segments.length} 个问题
                </span>
              )}
            </div>
            <p className="text-xs text-blue-600 mt-1">
              已根据检测结果自动选择优化策略
            </p>
          </div>
        )}

        {/* Strategy checkboxes */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            优化策略
          </label>
          <div className="grid grid-cols-2 gap-3">
            {strategies.map((s) => (
              <label
                key={s.value}
                className={`flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${
                  selected.includes(s.value)
                    ? "border-brand-500 bg-brand-50"
                    : "border-gray-200 hover:border-gray-300"
                }`}
              >
                <input
                  type="checkbox"
                  checked={selected.includes(s.value)}
                  onChange={() => toggle(s.value)}
                  className="mt-0.5 accent-brand-600"
                />
                <div>
                  <p className="text-sm font-medium text-gray-900">{s.label}</p>
                  <p className="text-xs text-gray-500">{s.desc}</p>
                </div>
              </label>
            ))}
          </div>
        </div>

        {/* Action buttons */}
        <div className="flex items-center gap-3 pt-2">
          <button
            className="btn-primary"
            disabled={loading || !text.trim() || selected.length === 0}
            onClick={handleSubmit}
          >
            {loading ? (
              <>
                <svg
                  className="animate-spin -ml-1 mr-2 h-4 w-4 text-white inline"
                  viewBox="0 0 24 24"
                >
                  <circle
                    className="opacity-25"
                    cx="12"
                    cy="12"
                    r="10"
                    stroke="currentColor"
                    strokeWidth="4"
                    fill="none"
                  />
                  <path
                    className="opacity-75"
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                  />
                </svg>
                分析中...
              </>
            ) : (
              "一键优化"
            )}
          </button>
          {textHistory.length > 0 && (
            <button
              type="button"
              className="btn-secondary"
              onClick={handleUndo}
            >
              撤销上次应用
            </button>
          )}
          {results.length > 0 && (
            <button
              type="button"
              className="btn-secondary"
              onClick={() => {
                setResults([]);
                setAccepted({});
              }}
            >
              重新优化
            </button>
          )}
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm">
          {error}
        </div>
      )}

      {/* Results */}
      {results.length > 0 && (
        <div className="card space-y-4">
          {/* Summary */}
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-semibold text-gray-900">
              优化建议
              <span className="text-sm font-normal text-gray-400 ml-2">
                共 {results.length} 条
              </span>
            </h3>
            <div className="flex items-center gap-3 text-sm">
              {originalRiskScore !== null && estimatedRiskScore !== null && (
                <span className="text-gray-500">
                  预计降低风险至{" "}
                  <span className="font-semibold text-green-600">
                    {(estimatedRiskScore * 100).toFixed(1)}%
                  </span>
                  <span className="text-gray-400 ml-1">
                    (原 {(originalRiskScore * 100).toFixed(1)}%)
                  </span>
                </span>
              )}
            </div>
          </div>

          {/* Batch actions */}
          <div className="flex items-center gap-3 pb-2 border-b border-gray-100">
            <button
              type="button"
              className="text-sm font-medium text-brand-600 hover:text-brand-700"
              onClick={handleAcceptAll}
            >
              全部接受
            </button>
            <button
              type="button"
              className={`btn-primary text-sm ${
                acceptedCount === 0 ? "opacity-50 cursor-not-allowed" : ""
              }`}
              disabled={acceptedCount === 0}
              onClick={handleApply}
            >
              应用选中建议 ({acceptedCount})
            </button>
          </div>

          {/* Suggestion cards */}
          <div className="space-y-4">
            {results.map((sug) => {
              const isAccepted = accepted[sug.suggestion_id] === true;
              return (
                <div
                  key={sug.suggestion_id}
                  className={`border rounded-lg overflow-hidden transition-colors ${
                    isAccepted
                      ? "border-green-300 bg-green-50/30"
                      : "border-gray-200"
                  }`}
                >
                  {/* Card header */}
                  <div className="flex items-center justify-between px-4 py-2 bg-gray-50 border-b border-gray-100">
                    <div className="flex items-center gap-2">
                      <span
                        className={`text-xs font-medium px-2 py-0.5 rounded-full ${
                          typeBadgeColors[sug.type] ?? "bg-gray-100 text-gray-700"
                        }`}
                      >
                        {typeLabels[sug.type] ?? sug.type}
                      </span>
                      {/* Confidence */}
                      <span className="text-xs text-gray-400">
                        置信度 {(sug.confidence * 100).toFixed(0)}%
                      </span>
                    </div>
                    {/* Accept / Reject buttons */}
                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        className={`px-3 py-1 text-xs rounded font-medium transition-colors ${
                          isAccepted
                            ? "bg-green-500 text-white"
                            : "bg-white border border-green-300 text-green-600 hover:bg-green-50"
                        }`}
                        onClick={() => handleAccept(sug.suggestion_id)}
                      >
                        &#10003; 接受
                      </button>
                      <button
                        type="button"
                        className={`px-3 py-1 text-xs rounded font-medium transition-colors ${
                          !isAccepted && accepted[sug.suggestion_id] !== undefined
                            ? "bg-white border border-gray-300 text-gray-500"
                            : "bg-white border border-red-300 text-red-500 hover:bg-red-50"
                        }`}
                        onClick={() => handleReject(sug.suggestion_id)}
                      >
                        &#10007; 拒绝
                      </button>
                    </div>
                  </div>

                  {/* Card body */}
                  <div className="p-4 space-y-2">
                    <div>
                      <span className="text-xs text-gray-400">原文</span>
                      <p className="text-sm text-gray-600 bg-red-50 rounded px-3 py-2 mt-1 line-through">
                        {sug.original_text}
                      </p>
                    </div>
                    <div>
                      <span className="text-xs text-gray-400">建议修改</span>
                      <p className="text-sm text-gray-900 bg-green-50 rounded px-3 py-2 mt-1">
                        {sug.suggested_text}
                      </p>
                    </div>
                    {sug.explanation && (
                      <p className="text-xs text-gray-500 italic">
                        {sug.explanation}
                      </p>
                    )}
                  </div>
                </div>
              );
            })}
          </div>

          {/* Bottom batch actions */}
          <div className="flex items-center gap-3 pt-3 border-t border-gray-100">
            <button
              type="button"
              className="text-sm font-medium text-brand-600 hover:text-brand-700"
              onClick={handleAcceptAll}
            >
              全部接受
            </button>
            <button
              type="button"
              className={`btn-primary text-sm ${
                acceptedCount === 0 ? "opacity-50 cursor-not-allowed" : ""
              }`}
              disabled={acceptedCount === 0}
              onClick={handleApply}
            >
              应用选中建议 ({acceptedCount})
            </button>
          </div>
        </div>
      )}

      {/* Preview section */}
      {previewHtml && results.length > 0 && (
        <div className="card space-y-3">
          <h3 className="text-lg font-semibold text-gray-900">预览效果</h3>
          <p className="text-xs text-gray-500">
            绿色高亮部分为接受的建议修改
          </p>
          <div
            className="text-sm text-gray-800 leading-relaxed bg-gray-50 rounded-lg p-4 whitespace-pre-wrap"
            dangerouslySetInnerHTML={{ __html: previewHtml }}
          />
        </div>
      )}
    </div>
  );
}

/* ---- Utility ---- */
function escapeHtml(str: string): string {
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}
