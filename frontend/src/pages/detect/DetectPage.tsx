import { useState, useRef, useCallback } from "react";
import {
  submitDetection,
  pollDetectionResult,
  submitFeedback,
} from "../../services/api";
import type { DetectResultData } from "../../services/api";
import RiskBadge from "../../components/RiskBadge";
import HeatmapBar from "../../components/HeatmapBar";

type Granularity = "document" | "paragraph" | "sentence";
type Language = "auto" | "zh" | "en";

const MIN_TEXT_LENGTH = 200;

const disciplines = [
  { value: "general", label: "通用" },
  { value: "politics", label: "政治学" },
  { value: "economics", label: "经济学" },
  { value: "sociology", label: "社会学" },
  { value: "law", label: "法学" },
];

export default function DetectPage() {
  /* ---- Input State ---- */
  const [text, setText] = useState("");
  const [granularity, setGranularity] = useState<Granularity>("paragraph");
  const [language, setLanguage] = useState<Language>("auto");
  const [discipline, setDiscipline] = useState("general");
  const fileRef = useRef<HTMLInputElement>(null);

  /* ---- Detection State ---- */
  const [loading, setLoading] = useState(false);
  const [progress, setProgress] = useState("");
  const [taskStatus, setTaskStatus] = useState<string>("");
  const [result, setResult] = useState<DetectResultData | null>(null);
  const [error, setError] = useState("");

  /* ---- Feedback State ---- */
  const [feedbackOpen, setFeedbackOpen] = useState(false);
  const [feedbackType, setFeedbackType] = useState<
    "agree" | "disagree" | "partial"
  >("agree");
  const [feedbackComment, setFeedbackComment] = useState("");
  const [feedbackSent, setFeedbackSent] = useState(false);

  const textTooShort = text.length > 0 && text.length < MIN_TEXT_LENGTH;

  /* ---- File upload handler ---- */
  const handleFile = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (!file) return;
      const reader = new FileReader();
      reader.onload = (ev) => {
        setText((ev.target?.result as string) ?? "");
      };
      reader.readAsText(file);
    },
    []
  );

  /* ---- Detect ---- */
  const handleDetect = async () => {
    if (!text.trim() || text.length < MIN_TEXT_LENGTH) return;
    setLoading(true);
    setResult(null);
    setError("");
    setFeedbackSent(false);
    setFeedbackOpen(false);
    setProgress("正在提交检测任务...");
    setTaskStatus("submitting");

    try {
      const task = await submitDetection(text, granularity, language, discipline);
      setTaskStatus("pending");
      setProgress("任务已提交，排队等待中...");

      const final = await pollDetectionResult(
        task.task_id,
        (status) => {
          setTaskStatus(status);
          setProgress(
            status === "processing"
              ? "AI模型分析中，请稍候..."
              : "排队等待中..."
          );
        },
        5000,
        60
      );

      setTaskStatus(final.status);

      if (final.status === "failed") {
        setError(final.error || "检测失败，请重试");
      } else {
        setResult(final);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "网络错误";
      setError(msg);
    } finally {
      setLoading(false);
      setProgress("");
      setTaskStatus("");
    }
  };

  /* ---- Feedback ---- */
  const handleFeedback = async () => {
    if (!result?.task_id) return;
    try {
      await submitFeedback(result.task_id, feedbackType, feedbackComment);
      setFeedbackSent(true);
      setFeedbackOpen(false);
    } catch {
      // silently fail for feedback
    }
  };

  return (
    <div className="max-w-4xl mx-auto px-6 py-8 space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold text-gray-900">AI 文本检测</h2>
        <p className="text-sm text-gray-500 mt-1">
          基于证据的学术文本AI生成检测，支持多粒度、多学科分析
        </p>
      </div>

      {/* Input Card */}
      <div className="card space-y-4">
        {/* Text area */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1.5">
            待检测文本
          </label>
          <textarea
            className="input min-h-[200px] resize-y"
            placeholder="在此粘贴需要检测的学术文本，或上传文件...（至少200字符）"
            value={text}
            onChange={(e) => setText(e.target.value)}
          />
          <div className="flex items-center justify-between mt-2">
            <span
              className={`text-xs ${
                textTooShort ? "text-red-500 font-medium" : "text-gray-400"
              }`}
            >
              {text.length} / {MIN_TEXT_LENGTH} 字符
              {textTooShort && `（还需 ${MIN_TEXT_LENGTH - text.length} 字符）`}
            </span>
            <button
              type="button"
              className="text-xs text-brand-600 hover:text-brand-700 font-medium"
              onClick={() => fileRef.current?.click()}
            >
              上传文件 (.txt / .docx)
            </button>
            <input
              ref={fileRef}
              type="file"
              accept=".txt,.docx,.md"
              className="hidden"
              onChange={handleFile}
            />
          </div>
        </div>

        {/* Options row */}
        <div className="grid grid-cols-3 gap-4">
          {/* Granularity */}
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">
              检测粒度
            </label>
            <select
              className="select"
              value={granularity}
              onChange={(e) => setGranularity(e.target.value as Granularity)}
            >
              <option value="document">整篇文档</option>
              <option value="paragraph">段落级别</option>
              <option value="sentence">句子级别</option>
            </select>
          </div>

          {/* Language */}
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">
              语言
            </label>
            <select
              className="select"
              value={language}
              onChange={(e) => setLanguage(e.target.value as Language)}
            >
              <option value="auto">自动检测</option>
              <option value="zh">中文</option>
              <option value="en">英文</option>
            </select>
          </div>

          {/* Discipline */}
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">
              学科领域
            </label>
            <select
              className="select"
              value={discipline}
              onChange={(e) => setDiscipline(e.target.value)}
            >
              {disciplines.map((d) => (
                <option key={d.value} value={d.value}>
                  {d.label}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Submit */}
        <div className="flex items-center gap-3 pt-2">
          <button
            className="btn-primary"
            disabled={loading || !text.trim() || text.length < MIN_TEXT_LENGTH}
            onClick={handleDetect}
          >
            {loading ? (
              <>
                <svg
                  className="animate-spin -ml-1 mr-2 h-4 w-4 text-white"
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
                检测中...
              </>
            ) : (
              "开始检测"
            )}
          </button>
          {loading && (
            <span className="text-sm text-gray-500">{progress}</span>
          )}
        </div>
      </div>

      {/* Status indicator while polling */}
      {loading && taskStatus && (
        <div className="card flex items-center gap-4 py-4">
          <div className="relative h-10 w-10">
            <svg
              className="animate-spin h-10 w-10 text-brand-500"
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
          </div>
          <div>
            <p className="text-sm font-medium text-gray-900">
              {taskStatus === "pending" && "排队等待中..."}
              {taskStatus === "processing" && "AI模型分析中..."}
              {taskStatus === "submitting" && "正在提交..."}
            </p>
            <p className="text-xs text-gray-500 mt-0.5">
              {taskStatus === "pending" && "任务已进入队列，等待处理"}
              {taskStatus === "processing" && "正在运行检测模型，请耐心等待"}
              {taskStatus === "submitting" && "正在连接服务器"}
            </p>
          </div>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm">
          {error}
        </div>
      )}

      {/* Results */}
      {result && (
        <div className="card space-y-6">
          <h3 className="text-lg font-semibold text-gray-900">检测结果</h3>

          {/* Top-level metrics */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="bg-gray-50 rounded-lg p-4 text-center">
              <p className="text-xs text-gray-500 mb-2">风险等级</p>
              <RiskBadge level={result.risk_level ?? "low"} size="lg" />
            </div>
            <div className="bg-gray-50 rounded-lg p-4 text-center">
              <p className="text-xs text-gray-500 mb-2">风险分数</p>
              <p className="text-2xl font-bold text-gray-900">
                {result.risk_score !== undefined
                  ? (result.risk_score * 100).toFixed(1)
                  : "N/A"}
                <span className="text-sm font-normal text-gray-400">%</span>
              </p>
            </div>
            <div className="bg-gray-50 rounded-lg p-4 text-center">
              <p className="text-xs text-gray-500 mb-2">LLM 置信度</p>
              <p className="text-2xl font-bold text-gray-900">
                {result.llm_confidence !== undefined
                  ? (result.llm_confidence * 100).toFixed(1)
                  : "N/A"}
                <span className="text-sm font-normal text-gray-400">%</span>
              </p>
            </div>
            <div className="bg-gray-50 rounded-lg p-4 text-center">
              <p className="text-xs text-gray-500 mb-2">统计特征分数</p>
              <p className="text-2xl font-bold text-gray-900">
                {result.statistical_score !== undefined
                  ? (result.statistical_score * 100).toFixed(1)
                  : "N/A"}
                <span className="text-sm font-normal text-gray-400">%</span>
              </p>
            </div>
          </div>

          {/* Evidence completeness */}
          {result.evidence_completeness !== undefined && (
            <div className="bg-gray-50 rounded-lg p-4">
              <div className="flex items-center justify-between mb-2">
                <p className="text-xs text-gray-500">证据完备度</p>
                <p className="text-sm font-semibold text-gray-700">
                  {(result.evidence_completeness * 100).toFixed(0)}%
                </p>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-2">
                <div
                  className="bg-brand-500 h-2 rounded-full transition-all"
                  style={{
                    width: `${(result.evidence_completeness * 100).toFixed(0)}%`,
                  }}
                />
              </div>
            </div>
          )}

          {/* Heatmap */}
          {result.paragraph_scores && result.paragraph_scores.length > 0 && (
            <div>
              <HeatmapBar paragraphs={result.paragraph_scores} />
            </div>
          )}

          {/* Evidence Summary */}
          {result.evidence_summary && (
            <div>
              <h4 className="text-sm font-semibold text-gray-700 mb-2">
                证据摘要
              </h4>
              <p className="text-sm text-gray-600 leading-relaxed bg-gray-50 rounded-lg p-4">
                {result.evidence_summary}
              </p>
            </div>
          )}

          {/* Recommendations */}
          {result.recommendations && result.recommendations.length > 0 && (
            <div>
              <h4 className="text-sm font-semibold text-gray-700 mb-2">
                建议措施
              </h4>
              <ul className="space-y-1.5">
                {result.recommendations.map((rec, i) => (
                  <li
                    key={i}
                    className="flex items-start gap-2 text-sm text-gray-600"
                  >
                    <span className="text-brand-500 mt-0.5">•</span>
                    {rec}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Uncertainty disclaimer */}
          {result.uncertainty_note && (
            <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 text-xs text-amber-700">
              <span className="font-semibold">不确定性声明：</span>
              {result.uncertainty_note}
            </div>
          )}

          {/* Actions */}
          <div className="flex items-center gap-3 pt-2 border-t border-gray-100">
            <button
              className="btn-secondary"
              onClick={() => setFeedbackOpen(!feedbackOpen)}
            >
              提交反馈
            </button>
            <button className="btn-secondary">申请复核</button>
            {feedbackSent && (
              <span className="text-xs text-green-600 font-medium">
                反馈已提交，感谢！
              </span>
            )}
          </div>

          {/* Feedback form */}
          {feedbackOpen && (
            <div className="border border-gray-200 rounded-lg p-4 space-y-3">
              <p className="text-sm font-medium text-gray-700">检测结果反馈</p>
              <div className="flex gap-3">
                {(
                  [
                    ["agree", "认同"],
                    ["partial", "部分认同"],
                    ["disagree", "不认同"],
                  ] as const
                ).map(([val, label]) => (
                  <label
                    key={val}
                    className="flex items-center gap-1.5 text-sm"
                  >
                    <input
                      type="radio"
                      name="feedback"
                      value={val}
                      checked={feedbackType === val}
                      onChange={() => setFeedbackType(val)}
                      className="accent-brand-600"
                    />
                    {label}
                  </label>
                ))}
              </div>
              <textarea
                className="input min-h-[80px]"
                placeholder="请说明您的看法（选填）"
                value={feedbackComment}
                onChange={(e) => setFeedbackComment(e.target.value)}
              />
              <button className="btn-primary" onClick={handleFeedback}>
                提交
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
