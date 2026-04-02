import { useState, useCallback, useMemo, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { getSuggestions, oneClickOptimize } from "../../services/api";
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
      return { text: "极高风险", className: "badge-red" };
    case "high":
      return { text: "高风险", className: "badge-red" };
    case "medium":
      return { text: "中风险", className: "badge-yellow" };
    case "low":
      return { text: "低风险", className: "badge-green" };
    default:
      return { text: level, className: "bg-gray-100 text-gray-700" };
  }
}

/* ---- Editable issue item for HITL checklist ---- */
interface EditableIssue {
  id: string;
  checked: boolean;
  snippet: string;
  issue: string;        // editable by user
  originalIssue: string; // original from detection
}

export default function SuggestPage() {
  const navigate = useNavigate();

  /* ---- State ---- */
  const [text, setText] = useState("");
  const [selected, setSelected] = useState<string[]>(() => {
    const stored = localStorage.getItem("sg_suggest_strategies");
    if (stored) {
      try { return JSON.parse(stored) as string[]; } catch { /* ignore */ }
    }
    return ["rephrase", "vocabulary"];
  });
  const [loading, setLoading] = useState(() => sessionStorage.getItem("sg_optimizing") === "true");
  const mountedRef = useRef(true);
  const [optimized, setOptimized] = useState(() => {
    // Check if optimization was already done with actual suggestions
    try {
      const log = sessionStorage.getItem("sg_revision_log");
      if (!log) return false;
      const parsed = JSON.parse(log);
      return Array.isArray(parsed) && parsed.length > 0;
    } catch {
      return false;
    }
  });
  const [results, setResults] = useState<SuggestionItem[]>([]);
  const [originalRiskScore, setOriginalRiskScore] = useState<number | null>(null);
  const [estimatedRiskScore, setEstimatedRiskScore] = useState<number | null>(null);
  const [error, setError] = useState("");

  // Persist strategy selections to localStorage
  useEffect(() => {
    localStorage.setItem("sg_suggest_strategies", JSON.stringify(selected));
  }, [selected]);

  // Detection context (imported from DetectPage)
  const [detectResult, setDetectResult] = useState<DetectResultData | null>(null);

  // HITL: editable issues checklist from detection
  const [editableIssues, setEditableIssues] = useState<EditableIssue[]>([]);
  const [customPrompt, setCustomPrompt] = useState("");
  const [issuesPanelOpen, setIssuesPanelOpen] = useState(true);

  // Auto-import detection text and result on mount (only when detection result exists)
  useEffect(() => {
    const storedResult = sessionStorage.getItem("sg_detect_result");

    if (storedResult) {
      const storedText = sessionStorage.getItem("sg_detect_text");
      if (storedText && !text) {
        setText(storedText);
      }
    }

    if (storedResult) {
      try {
        const parsed = JSON.parse(storedResult) as DetectResultData;
        setDetectResult(parsed);
        // Only auto-select strategies if user has no saved preference in localStorage
        const hasSavedStrategies = !!localStorage.getItem("sg_suggest_strategies");
        if (!hasSavedStrategies) {
          const autoStrategies = autoSelectStrategies(parsed);
          setSelected(autoStrategies);
        }
        // Build editable issues from flagged_segments
        const segments = parsed.flagged_segments ?? [];
        setEditableIssues(
          segments.map((seg, idx) => ({
            id: `issue-${idx}`,
            checked: true,
            snippet: seg.text_snippet,
            issue: seg.issue,
            originalIssue: seg.issue,
          }))
        );
      } catch {
        // Ignore parse errors
      }
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Track mount state for background optimization
  useEffect(() => {
    mountedRef.current = true;

    // If optimization completed while we were away, pick up the result
    if (sessionStorage.getItem("sg_optimizing") === "done") {
      sessionStorage.removeItem("sg_optimizing");
      setLoading(false);
      setOptimized(true);
      navigate(`/review?tab=optimization&_t=${Date.now()}`);
    }

    return () => { mountedRef.current = false; };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Accept/reject state per suggestion
  const [accepted, setAccepted] = useState<Record<string, boolean>>({});

  // Undo history
  const [textHistory, setTextHistory] = useState<string[]>([]);

  // Applied results: optimized text + revision log (for download)
  const [appliedText, setAppliedText] = useState<string | null>(null);
  const [revisionLog, setRevisionLog] = useState<SuggestionItem[]>([]);
  const [appliedTimestamp, setAppliedTimestamp] = useState("");

  /* ---- Helpers ---- */
  const toggle = (val: string) => {
    setSelected((prev) =>
      prev.includes(val) ? prev.filter((v) => v !== val) : [...prev, val]
    );
  };

  /* ---- Import from detection ---- */
  const handleImport = useCallback(() => {
    const storedResult = sessionStorage.getItem("sg_detect_result");

    if (!storedResult) {
      setError("没有找到检测结果，请先在检测页面完成检测。");
      return;
    }

    const storedText = sessionStorage.getItem("sg_detect_text");
    if (storedText) {
      setText(storedText);
    }

    if (storedResult) {
      try {
        const parsed = JSON.parse(storedResult) as DetectResultData;
        setDetectResult(parsed);
        const autoStrategies = autoSelectStrategies(parsed);
        setSelected(autoStrategies);
        // Rebuild editable issues
        const segments = parsed.flagged_segments ?? [];
        setEditableIssues(
          segments.map((seg, idx) => ({
            id: `issue-${idx}`,
            checked: true,
            snippet: seg.text_snippet,
            issue: seg.issue,
            originalIssue: seg.issue,
          }))
        );
      } catch {
        // Ignore parse errors
      }
    }

    setResults([]);
    setAccepted({});
    setCustomPrompt("");
    setError("");
    setOptimized(false);
    // Clear previous optimization results
    sessionStorage.removeItem("sg_optimized_text");
    sessionStorage.removeItem("sg_revision_log");
    sessionStorage.removeItem("sg_revision_timestamp");
  }, []);

  /* ---- Build user-curated issues for submission ---- */
  const checkedIssues = useMemo(() => {
    return editableIssues
      .filter((i) => i.checked)
      .map((i) => ({
        snippet: i.snippet,
        issue: i.issue,
      }));
  }, [editableIssues]);

  const checkedCount = editableIssues.filter((i) => i.checked).length;

  /* ---- HITL issue handlers ---- */
  const toggleIssue = (id: string) => {
    setEditableIssues((prev) =>
      prev.map((i) => (i.id === id ? { ...i, checked: !i.checked } : i))
    );
  };

  const updateIssueText = (id: string, newText: string) => {
    setEditableIssues((prev) =>
      prev.map((i) => (i.id === id ? { ...i, issue: newText } : i))
    );
  };

  const selectAllIssues = () => {
    setEditableIssues((prev) => prev.map((i) => ({ ...i, checked: true })));
  };

  const deselectAllIssues = () => {
    setEditableIssues((prev) => prev.map((i) => ({ ...i, checked: false })));
  };

  /* ---- Submit for suggestions ---- */
  const handleSubmit = async () => {
    if (!text.trim() || selected.length === 0) return;
    setLoading(true);
    sessionStorage.setItem("sg_optimizing", "true");
    setError("");
    setResults([]);
    setAccepted({});
    try {
      const detectionId = detectResult?.task_id;

      // If we have a detection_id, use one-click optimize (persists to DB)
      if (detectionId) {
        const optimizeResult = await oneClickOptimize(
          text,
          detectionId,
          checkedIssues.length > 0 ? checkedIssues : [],
          selected
        );

        const suggestions = optimizeResult.suggestions;
        if (suggestions.length === 0) {
          sessionStorage.removeItem("sg_optimizing");
          if (mountedRef.current) {
            setResults([]);
            setError("未生成任何优化建议，请调整策略后重试。");
            setLoading(false);
          }
          return;
        }

        // Always persist to sessionStorage (survives navigation)
        sessionStorage.setItem("sg_optimized_text", optimizeResult.optimized_text);
        sessionStorage.setItem("sg_original_text", text);
        sessionStorage.setItem("sg_revision_log", JSON.stringify(suggestions));
        sessionStorage.setItem("sg_revision_timestamp", optimizeResult.timestamp);

        if (mountedRef.current) {
          setResults(suggestions);
          setOriginalRiskScore(optimizeResult.original_risk_score);
          setEstimatedRiskScore(optimizeResult.estimated_risk_score);
          setOptimized(true);
          setLoading(false);
          sessionStorage.removeItem("sg_optimizing");
          navigate(`/review?tab=optimization&_t=${Date.now()}`);
        } else {
          // Component unmounted — mark done so remount can pick it up
          sessionStorage.setItem("sg_optimizing", "done");
        }
        return;
      }

      // Fallback: no detection context, use basic suggest endpoint
      const res = await getSuggestions(
        text,
        selected,
        undefined,
        undefined,
        undefined,
        checkedIssues.length > 0 ? checkedIssues : undefined,
        customPrompt.trim() || undefined
      );

      const suggestions = res.suggestions;

      if (suggestions.length === 0) {
        sessionStorage.removeItem("sg_optimizing");
        if (mountedRef.current) {
          setResults([]);
          setError("未生成任何优化建议，请调整策略后重试。");
          setLoading(false);
        }
        return;
      }

      const sorted = [...suggestions].sort(
        (a, b) => b.offset_start - a.offset_start
      );

      let newText = text;
      for (const s of sorted) {
        const before = newText.slice(0, s.offset_start);
        const after = newText.slice(s.offset_end);
        newText = before + s.suggested_text + after;
      }

      const timestamp = new Date().toLocaleString("zh-CN");

      // Always persist to sessionStorage (survives navigation)
      sessionStorage.setItem("sg_optimized_text", newText);
      sessionStorage.setItem("sg_original_text", text);
      sessionStorage.setItem("sg_revision_log", JSON.stringify(suggestions));
      sessionStorage.setItem("sg_revision_timestamp", timestamp);

      if (mountedRef.current) {
        setResults(suggestions);
        setOriginalRiskScore(res.original_risk_score);
        setEstimatedRiskScore(res.estimated_risk_score);
        setLoading(false);
        sessionStorage.removeItem("sg_optimizing");
        navigate(`/review?tab=optimization&_t=${Date.now()}`);
      } else {
        sessionStorage.setItem("sg_optimizing", "done");
      }
      return;
    } catch (err: unknown) {
      sessionStorage.removeItem("sg_optimizing");
      if (mountedRef.current) {
        const axiosErr = err as { response?: { data?: { detail?: string } } };
        const detail = axiosErr?.response?.data?.detail;
        setError(detail || (err instanceof Error ? err.message : "请求失败"));
        setLoading(false);
      }
      return;
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

    const timestamp = new Date().toLocaleString("zh-CN");

    // Save revision log before clearing results
    setRevisionLog([...acceptedSuggestions]);
    setAppliedTimestamp(timestamp);

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
    setAppliedText(newText);

    // Save to sessionStorage for ReviewPage
    sessionStorage.setItem("sg_optimized_text", newText);
    sessionStorage.setItem("sg_original_text", text);
    sessionStorage.setItem("sg_revision_log", JSON.stringify(acceptedSuggestions));
    sessionStorage.setItem("sg_revision_timestamp", timestamp);

    setResults([]);
    setAccepted({});

    // Navigate to review page, optimization results tab
    // Add timestamp to ensure searchParams always changes → triggers useEffect in ReviewPage
    navigate(`/review?tab=optimization&_t=${Date.now()}`);
  }, [text, acceptedSuggestions, acceptedCount, navigate]);

  /* ---- Undo ---- */
  const handleUndo = useCallback(() => {
    if (textHistory.length === 0) return;
    const prev = textHistory[textHistory.length - 1];
    setTextHistory((h) => h.slice(0, -1));
    setText(prev);
    setResults([]);
    setAccepted({});
    setAppliedText(null);
    setRevisionLog([]);
  }, [textHistory]);

  /* ---- Issues checklist from detection ---- */
  const issuesSummary = useMemo(() => {
    if (!detectResult) return null;

    const items: { category: string; icon: string; color: string; details: string[] }[] = [];

    // Overall risk
    if (detectResult.risk_score !== undefined || detectResult.nhpr_score !== undefined) {
      const details: string[] = [];
      if (detectResult.nhpr_score !== undefined) {
        details.push(`非人特征占比 (NHPR)：${(detectResult.nhpr_score * 100).toFixed(1)}%` +
          (detectResult.nhpr_level ? ` — ${riskLevelLabel(detectResult.nhpr_level).text}` : ""));
      }
      if (detectResult.risk_score !== undefined) {
        details.push(`AI相似度：${(detectResult.risk_score * 100).toFixed(1)}%` +
          (detectResult.risk_level ? ` — ${riskLevelLabel(detectResult.risk_level).text}` : ""));
      }
      if (detectResult.llm_confidence !== undefined) {
        details.push(`LLM判定置信度：${(detectResult.llm_confidence * 100).toFixed(1)}%`);
      }
      if (detectResult.statistical_score !== undefined) {
        details.push(`统计分析分数：${(detectResult.statistical_score * 100).toFixed(1)}%`);
      }
      items.push({ category: "综合评估", icon: "📊", color: "blue", details });
    }

    // Flagged segments grouped by issue type
    const segments = detectResult.flagged_segments ?? [];
    if (segments.length > 0) {
      const grouped: Record<string, string[]> = {};
      for (const seg of segments) {
        const issue = seg.issue || "未分类问题";
        if (!grouped[issue]) grouped[issue] = [];
        const snippet = seg.text_snippet.length > 40
          ? seg.text_snippet.slice(0, 40) + "..."
          : seg.text_snippet;
        grouped[issue].push(`"${snippet}"`);
      }
      for (const [issue, snippets] of Object.entries(grouped)) {
        const iconMap: Record<string, string> = {
          "结构": "🏗️", "逻辑": "🔗", "表达": "✏️", "自然": "🌿",
          "生硬": "🪨", "词汇": "📝", "用词": "📝", "语气": "🎭",
          "模板": "📋", "平滑": "📉", "概率": "📈",
        };
        let icon = "⚠️";
        for (const [key, val] of Object.entries(iconMap)) {
          if (issue.includes(key)) { icon = val; break; }
        }
        items.push({
          category: `${issue}（${snippets.length}处）`,
          icon,
          color: "amber",
          details: snippets,
        });
      }
    }

    // Paragraph-level issues
    const highRiskParas = (detectResult.paragraph_scores ?? []).filter(
      (p) => p.risk_level === "high" || p.risk_level === "critical"
    );
    if (highRiskParas.length > 0) {
      items.push({
        category: `高风险段落（${highRiskParas.length}段）`,
        icon: "🔴",
        color: "red",
        details: highRiskParas.map((p) => {
          const preview = p.text.length > 50 ? p.text.slice(0, 50) + "..." : p.text;
          return `第${p.index + 1}段 (${(p.score * 100).toFixed(0)}%)：${preview}`;
        }),
      });
    }

    // Evidence summary
    if (detectResult.evidence_summary) {
      items.push({
        category: "证据分析摘要",
        icon: "🔍",
        color: "purple",
        details: [detectResult.evidence_summary],
      });
    }

    // Recommendations
    if (detectResult.recommendations && detectResult.recommendations.length > 0) {
      items.push({
        category: "改进建议",
        icon: "💡",
        color: "green",
        details: detectResult.recommendations,
      });
    }

    return items.length > 0 ? items : null;
  }, [detectResult]);

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
        <h2 className="text-xl font-bold text-gray-900 tracking-tight">写作建议</h2>
        <p className="text-[13px] text-gray-400 mt-1">
          获取改善文本自然度和学术质量的建议，自动导入最近一次检测的文本与结果
        </p>
      </div>

      {/* Input Card */}
      <div className="card space-y-4">
        {/* Text area with import button */}
        <div>
          <div className="flex items-center justify-between mb-1.5">
            <label className="label">
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
          <div className="bg-blue-50 border border-blue-200 rounded-2xl p-4">
            <div className="flex items-center gap-3 flex-wrap">
              <span className="text-sm font-medium text-blue-800">
                已导入检测结果
              </span>
              {(detectResult.nhpr_level ?? detectResult.risk_level) && (
                <span
                  className={`text-xs font-medium px-2 py-0.5 rounded-full ${
                    riskLevelLabel(detectResult.nhpr_level ?? detectResult.risk_level ?? "low").className
                  }`}
                >
                  {riskLevelLabel(detectResult.nhpr_level ?? detectResult.risk_level ?? "low").text}
                </span>
              )}
              {detectResult.nhpr_score !== undefined && (
                <span className="text-xs text-blue-700">
                  AI特征占比：{(detectResult.nhpr_score * 100).toFixed(1)}%
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

        {/* HITL Issues Checklist Panel */}
        {editableIssues.length > 0 && (
          <div className="border border-orange-200 rounded-2xl overflow-hidden">
            <button
              type="button"
              className="w-full flex items-center justify-between px-4 py-3 bg-orange-50 hover:bg-orange-100 transition-colors"
              onClick={() => setIssuesPanelOpen((v) => !v)}
            >
              <div className="flex items-center gap-2">
                <svg className="w-4 h-4 text-orange-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" /></svg>
                <span className="text-sm font-bold text-gray-700">
                  检测问题清单
                </span>
                <span className="text-xs text-orange-600">
                  已选 {checkedCount}/{editableIssues.length} 项
                </span>
              </div>
              <span className="text-orange-400 text-sm">
                {issuesPanelOpen ? "▲ 收起" : "▼ 展开"}
              </span>
            </button>
            {issuesPanelOpen && (
              <div className="bg-white">
                {/* Batch select controls */}
                <div className="flex items-center gap-3 px-4 py-2 border-b border-orange-100 bg-orange-50/50">
                  <button
                    type="button"
                    className="text-xs font-medium text-orange-700 hover:text-orange-900"
                    onClick={selectAllIssues}
                  >
                    全选
                  </button>
                  <span className="text-orange-300">|</span>
                  <button
                    type="button"
                    className="text-xs font-medium text-orange-700 hover:text-orange-900"
                    onClick={deselectAllIssues}
                  >
                    全不选
                  </button>
                  <span className="ml-auto text-xs text-gray-400">
                    勾选要优化的问题，可编辑问题描述以指导优化方向
                  </span>
                </div>

                {/* Issue items */}
                <div className="max-h-[400px] overflow-y-auto divide-y divide-gray-100">
                  {editableIssues.map((item) => (
                    <div
                      key={item.id}
                      className={`px-4 py-3 transition-colors ${
                        item.checked ? "bg-white" : "bg-gray-50 opacity-60"
                      }`}
                    >
                      <div className="flex items-start gap-3">
                        <input
                          type="checkbox"
                          checked={item.checked}
                          onChange={() => toggleIssue(item.id)}
                          className="mt-1 accent-orange-500 flex-shrink-0"
                        />
                        <div className="flex-1 min-w-0 space-y-1.5">
                          {/* Snippet preview */}
                          <p className="text-xs text-gray-500 truncate" title={item.snippet}>
                            <span className="text-gray-400 mr-1">原文：</span>
                            &ldquo;{item.snippet.length > 60
                              ? item.snippet.slice(0, 60) + "..."
                              : item.snippet}&rdquo;
                          </p>
                          {/* Editable issue description */}
                          <div className="flex items-start gap-2">
                            <span className="text-xs text-orange-600 mt-1 flex-shrink-0">问题：</span>
                            <input
                              type="text"
                              value={item.issue}
                              onChange={(e) => updateIssueText(item.id, e.target.value)}
                              disabled={!item.checked}
                              className={`flex-1 text-xs border rounded-xl px-2 py-1 transition-colors ${
                                item.checked
                                  ? "border-orange-200 bg-white text-gray-800 focus:border-orange-400 focus:ring-1 focus:ring-orange-200"
                                  : "border-gray-200 bg-gray-100 text-gray-400 cursor-not-allowed"
                              }`}
                              title="可编辑此问题描述以指导优化方向"
                            />
                            {item.issue !== item.originalIssue && item.checked && (
                              <button
                                type="button"
                                className="text-xs text-gray-400 hover:text-gray-600 mt-1 flex-shrink-0"
                                onClick={() => updateIssueText(item.id, item.originalIssue)}
                                title="恢复原始描述"
                              >
                                ↩
                              </button>
                            )}
                          </div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>

                {/* Custom prompt input */}
                <div className="px-4 py-3 border-t border-orange-100 bg-orange-50/30">
                  <label className="label">
                    补充提示（可选）
                  </label>
                  <textarea
                    className="input text-xs resize-y"
                    rows={2}
                    placeholder="在此输入额外的优化要求，例如：&quot;保持原文的学术正式性&quot;、&quot;重点改善第二段的论证逻辑&quot;、&quot;不要改变专业术语&quot;..."
                    value={customPrompt}
                    onChange={(e) => setCustomPrompt(e.target.value)}
                  />
                </div>
              </div>
            )}
          </div>
        )}

        {/* Overall detection summary (when no segments but has scores) */}
        {issuesSummary && editableIssues.length === 0 && (
          <div className="border border-blue-200 rounded-2xl overflow-hidden">
            <div className="px-4 py-3 bg-blue-50">
              <div className="flex items-center gap-2 mb-2">
                <svg className="w-4 h-4 text-blue-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" /></svg>
                <span className="text-sm font-bold text-gray-700">检测评估概览</span>
              </div>
              <div className="space-y-1">
                {issuesSummary.map((item, idx) => (
                  <div key={idx}>
                    <span className="text-xs text-blue-700">{item.icon} {item.category}：</span>
                    {item.details.map((d, di) => (
                      <span key={di} className="text-xs text-blue-600 ml-1">{d}</span>
                    ))}
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Strategy checkboxes */}
        <div>
          <label className="label">
            优化策略
          </label>
          <div className="grid grid-cols-2 gap-3">
            {strategies.map((s) => (
              <label
                key={s.value}
                className={`flex items-start gap-3 p-3 rounded-xl border cursor-pointer transition-colors ${
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
            className={`btn-primary ${optimized ? "opacity-50 cursor-not-allowed" : ""}`}
            disabled={loading || optimized || !text.trim() || selected.length === 0}
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
            ) : optimized ? (
              "已完成优化"
            ) : (
              "一键优化"
            )}
          </button>
          {optimized && (
            <button
              className="btn-secondary"
              onClick={() => navigate(`/review?tab=optimization&_t=${Date.now()}`)}
            >
              查看优化结果
            </button>
          )}
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
        <div className="bg-red-50 border border-red-100 text-red-600 px-5 py-3.5 rounded-2xl text-sm flex items-center gap-2.5">
          <svg className="w-4 h-4 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
          {error}
        </div>
      )}

      {/* Results */}
      {results.length > 0 && (
        <div className="card space-y-4">
          {/* Summary */}
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-bold text-gray-700 mb-2">
              优化建议
              <span className="text-xs font-normal text-gray-400 ml-2">
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
                  className={`border rounded-2xl overflow-hidden transition-colors ${
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
                        className={`px-3 py-1 text-xs rounded-xl font-medium transition-colors ${
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
                        className={`px-3 py-1 text-xs rounded-xl font-medium transition-colors ${
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
                      <span className="label">原文</span>
                      <p className="text-sm text-gray-600 bg-red-50 rounded-xl px-3 py-2 mt-1 line-through">
                        {sug.original_text}
                      </p>
                    </div>
                    <div>
                      <span className="label">建议修改</span>
                      <p className="text-sm text-gray-900 bg-green-50 rounded-xl px-3 py-2 mt-1">
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
          <h3 className="text-sm font-bold text-gray-700 mb-2">预览效果</h3>
          <p className="text-xs text-gray-500">
            绿色高亮部分为接受的建议修改
          </p>
          <div
            className="text-sm text-gray-800 leading-relaxed bg-gray-50 rounded-2xl p-4 whitespace-pre-wrap"
            dangerouslySetInnerHTML={{ __html: previewHtml }}
          />
        </div>
      )}

      {/* Optimization results are shown in Review Center after applying */}
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
