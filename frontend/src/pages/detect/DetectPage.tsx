import { useState, useRef, useCallback, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import mammoth from "mammoth";
import * as pdfjsLib from "pdfjs-dist";
import {
  submitDetection,
  pollDetectionResult,
  submitFeedback,
  checkOcrAvailability,
  performOcr,
} from "../../services/api";
import type { DetectResultData } from "../../services/api";
import RiskBadge from "../../components/RiskBadge";
import HeatmapBar from "../../components/HeatmapBar";
import HighlightedText from "../../components/HighlightedText";

// PDF.js worker — use static file from public/ directory
pdfjsLib.GlobalWorkerOptions.workerSrc = "/pdf.worker.min.mjs";

type Granularity = "document" | "paragraph" | "sentence";
type Language = "auto" | "zh" | "en";

const MIN_TEXT_LENGTH = 200;
const STORAGE_KEY = "sg_detect_text";

const disciplines = [
  { value: "general", label: "通用" },
  { value: "law", label: "法学" },
  { value: "management", label: "管理学" },
  { value: "education", label: "教育学" },
  { value: "economics", label: "经济学" },
  { value: "history", label: "历史学" },
  { value: "sociology", label: "社会学" },
  { value: "lis", label: "图书馆学情报学" },
  { value: "literary_criticism", label: "文学批评" },
  { value: "arts", label: "艺术研究" },
  { value: "politics", label: "政治学" },
];

export default function DetectPage() {
  const navigate = useNavigate();

  /* ---- Input State (restore from storage) ---- */
  const [text, setText] = useState(() => sessionStorage.getItem(STORAGE_KEY) || "");
  const [granularity, setGranularity] = useState<Granularity>(
    () => (localStorage.getItem("sg_detect_granularity") as Granularity) || "paragraph"
  );
  const [language, setLanguage] = useState<Language>(
    () => (localStorage.getItem("sg_detect_language") as Language) || "auto"
  );
  const [discipline, setDiscipline] = useState(
    () => localStorage.getItem("sg_detect_discipline") || "general"
  );
  const fileRef = useRef<HTMLInputElement>(null);

  /* Persist text to sessionStorage on every change */
  useEffect(() => {
    sessionStorage.setItem(STORAGE_KEY, text);
  }, [text]);

  /* Persist detection settings to localStorage */
  useEffect(() => {
    localStorage.setItem("sg_detect_granularity", granularity);
  }, [granularity]);
  useEffect(() => {
    localStorage.setItem("sg_detect_language", language);
  }, [language]);
  useEffect(() => {
    localStorage.setItem("sg_detect_discipline", discipline);
  }, [discipline]);

  /* ---- Detection State ---- */
  const [loading, setLoading] = useState(() => !!sessionStorage.getItem("sg_pending_task_id"));
  const [progress, setProgress] = useState(() =>
    sessionStorage.getItem("sg_pending_task_id") ? "检测进行中..." : ""
  );
  const [taskStatus, setTaskStatus] = useState<string>(() =>
    sessionStorage.getItem("sg_pending_task_id") ? "processing" : ""
  );
  const [result, setResult] = useState<DetectResultData | null>(() => {
    try {
      const saved = sessionStorage.getItem("sg_detect_result");
      return saved ? JSON.parse(saved) : null;
    } catch {
      return null;
    }
  });
  const [error, setError] = useState("");
  const mountedRef = useRef(true);

  /* ---- Feedback State ---- */
  const [feedbackOpen, setFeedbackOpen] = useState(false);
  const [feedbackType, setFeedbackType] = useState<
    "agree" | "disagree" | "partial"
  >("agree");
  const [feedbackComment, setFeedbackComment] = useState("");
  const [feedbackSent, setFeedbackSent] = useState(false);

  const textTooShort = text.length > 0 && text.length < MIN_TEXT_LENGTH;

  /* ---- PDF parsing / OCR state ---- */
  const [fileLoading, setFileLoading] = useState(false);
  const [ocrLoading, setOcrLoading] = useState(false);
  const [ocrAccuracy, setOcrAccuracy] = useState<{ estimate: number; note: string } | null>(null);

  /* ---- File upload handler ---- */
  const handleFile = useCallback(
    async (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (!file) return;

      const ext = file.name.split(".").pop()?.toLowerCase();
      setError("");
      setFileLoading(true);

      try {
        if (ext === "pdf") {
          // PDF: 先用 pdf.js 提取纯文本
          const arrayBuffer = await file.arrayBuffer();
          const pdf = await pdfjsLib.getDocument({ data: arrayBuffer }).promise;
          const pages: string[] = [];
          for (let i = 1; i <= pdf.numPages; i++) {
            const page = await pdf.getPage(i);
            const content = await page.getTextContent();
            const pageText = content.items
              .map((item) => ("str" in item ? (item as { str: string }).str : ""))
              .join("");
            if (pageText.trim()) pages.push(pageText);
          }
          const fullText = pages.join("\n\n");
          if (!fullText.trim()) {
            // pdf.js 无法提取文本 → 尝试 OCR
            setFileLoading(false);
            setOcrAccuracy(null);
            try {
              // 先检查 OCR 是否可用
              const ocrCheck = await checkOcrAvailability();
              if (!ocrCheck.available) {
                setError(
                  "PDF 文件未能提取到文本内容。如果是扫描件/图片型 PDF，请先 OCR 后再上传。"
                );
                e.target.value = "";
                return;
              }
              // 开始 OCR
              setOcrLoading(true);
              const ocrResult = await performOcr(file);
              setOcrLoading(false);
              if (ocrResult.text && ocrResult.text.trim()) {
                setText(ocrResult.text);
                setOcrAccuracy({
                  estimate: ocrResult.accuracy_estimate,
                  note: ocrResult.accuracy_note,
                });
              } else {
                setError("OCR 识别完成，但未能从 PDF 中提取到文字内容。");
              }
            } catch (ocrErr) {
              setOcrLoading(false);
              const ocrMsg = ocrErr instanceof Error ? ocrErr.message : "OCR 处理失败";
              // 503 = OCR not configured
              if (ocrMsg.includes("503") || ocrMsg.includes("OCR模型未配置")) {
                setError(
                  "PDF 文件未能提取到文本内容。如果是扫描件/图片型 PDF，请先 OCR 后再上传。"
                );
              } else {
                setError(`OCR 处理失败：${ocrMsg}`);
              }
            }
          } else {
            setText(fullText);
            setOcrAccuracy(null);
          }
        } else if (ext === "docx") {
          // .docx 是 ZIP 压缩的 XML，需要用 mammoth 解析
          const arrayBuffer = await file.arrayBuffer();
          const result = await mammoth.extractRawText({ arrayBuffer });
          setText(result.value);
        } else {
          // .txt / .md 等纯文本文件
          const reader = new FileReader();
          reader.onload = (ev) => {
            setText((ev.target?.result as string) ?? "");
            setFileLoading(false);
          };
          reader.readAsText(file, "utf-8");
          // reset input and return early (FileReader is async via callback)
          e.target.value = "";
          return;
        }
      } catch (err) {
        const msg = err instanceof Error ? err.message : "文件解析失败";
        setError(`文件解析失败：${msg}。请尝试复制粘贴文本内容。`);
      } finally {
        setFileLoading(false);
      }

      // 重置 input 以便再次选择同一文件
      e.target.value = "";
    },
    []
  );

  /**
   * Poll a task and persist result to sessionStorage.
   * Safe to call whether or not the component is still mounted —
   * it always writes to sessionStorage, and only touches React state
   * when the component is still mounted.
   */
  const runPolling = useCallback(
    async (taskId: string) => {
      try {
        const final = await pollDetectionResult(
          taskId,
          (status) => {
            if (!mountedRef.current) return;
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

        // Always persist to sessionStorage (survives navigation)
        sessionStorage.removeItem("sg_pending_task_id");
        if (final.status === "failed") {
          if (mountedRef.current) {
            setError(final.error || "检测失败，请重试");
          }
        } else {
          sessionStorage.setItem("sg_detect_result", JSON.stringify(final));
          if (mountedRef.current) {
            setResult(final);
          }
        }
      } catch (err: unknown) {
        sessionStorage.removeItem("sg_pending_task_id");
        if (mountedRef.current) {
          const msg = err instanceof Error ? err.message : "网络错误";
          setError(msg);
        }
      } finally {
        if (mountedRef.current) {
          setLoading(false);
          setProgress("");
          setTaskStatus("");
        }
      }
    },
    [] // eslint-disable-line react-hooks/exhaustive-deps
  );

  /* ---- Resume polling on mount if a task is in progress ---- */
  useEffect(() => {
    mountedRef.current = true;
    const pendingTaskId = sessionStorage.getItem("sg_pending_task_id");
    if (pendingTaskId && pendingTaskId !== "__submitting__") {
      // Real task ID — resume polling
      setLoading(true);
      setProgress("检测进行中...");
      setTaskStatus("processing");
      runPolling(pendingTaskId);
    } else if (pendingTaskId === "__submitting__") {
      // Task is still being submitted (API call in flight) — show loading
      setLoading(true);
      setProgress("正在提交检测任务...");
      setTaskStatus("submitting");
    }
    return () => {
      mountedRef.current = false;
    };
  }, [runPolling]);

  /* ---- Detect ---- */
  const handleDetect = async () => {
    if (!text.trim() || text.length < MIN_TEXT_LENGTH) return;
    setLoading(true);
    setResult(null);
    setError("");
    setFeedbackSent(false);
    setFeedbackOpen(false);
    setProgress("正在提交检测任务...");

    // Clear previous detection result and all downstream data (suggestions, review, etc.)
    sessionStorage.removeItem("sg_detect_result");
    sessionStorage.removeItem("sg_optimized_text");
    sessionStorage.removeItem("sg_original_text");
    sessionStorage.removeItem("sg_revision_log");
    sessionStorage.removeItem("sg_revision_timestamp");
    setTaskStatus("submitting");

    // Mark detection as in-progress immediately so navigation won't lose state
    sessionStorage.setItem("sg_pending_task_id", "__submitting__");

    try {
      // Save detection parameters for report page
      sessionStorage.setItem("sg_detect_params", JSON.stringify({ granularity, language, discipline }));

      const task = await submitDetection(text, granularity, language, discipline);

      // Update with real task ID for polling
      sessionStorage.setItem("sg_pending_task_id", task.task_id);

      if (mountedRef.current) {
        setTaskStatus("pending");
        setProgress("任务已提交，排队等待中...");
      }

      await runPolling(task.task_id);
    } catch (err: unknown) {
      sessionStorage.removeItem("sg_pending_task_id");
      const msg = err instanceof Error ? err.message : "网络错误";
      if (mountedRef.current) {
        setError(msg);
        setLoading(false);
        setProgress("");
        setTaskStatus("");
      }
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
        <h2 className="text-xl font-bold text-gray-900 tracking-tight">AI 文本检测</h2>
        <p className="text-[13px] text-gray-400 mt-1">
          基于证据的学术文本 AI 生成检测，支持多粒度、多学科分析
        </p>
      </div>

      {/* Input Card */}
      <div className="card space-y-4">
        {/* Text area */}
        <div>
          <label className="label">待检测文本</label>
          <textarea
            className="input min-h-[200px] resize-y !rounded-2xl"
            placeholder="在此粘贴需要检测的学术文本，或上传 PDF / Word / TXT 文件...（至少200字符）"
            value={text}
            onChange={(e) => setText(e.target.value)}
          />
          <div className="flex items-center justify-between mt-2">
            <span
              className={`text-xs ${
                textTooShort ? "text-red-500 font-medium" : "text-gray-400"
              }`}
            >
              {text.length} / {MIN_TEXT_LENGTH}（最少）字符
              {textTooShort && `（还需 ${MIN_TEXT_LENGTH - text.length} 字符）`}
            </span>
            <div className="flex items-center gap-3">
              {text.length > 0 && (
                <button
                  type="button"
                  className="text-xs text-red-400 hover:text-red-600 font-semibold transition-colors"
                  onClick={() => {
                    setText("");
                    sessionStorage.removeItem(STORAGE_KEY);
                    setResult(null);
                    setError("");
                    setOcrAccuracy(null);
                    // Clear detection result and all downstream data
                    sessionStorage.removeItem("sg_detect_result");
                    sessionStorage.removeItem("sg_detect_params");
                    sessionStorage.removeItem("sg_pending_task_id");
                    sessionStorage.removeItem("sg_optimized_text");
                    sessionStorage.removeItem("sg_original_text");
                    sessionStorage.removeItem("sg_revision_log");
                    sessionStorage.removeItem("sg_revision_timestamp");
                    setLoading(false);
                    setProgress("");
                    setTaskStatus("");
                  }}
                >
                  清空文本
                </button>
              )}
              <button
                type="button"
                className="text-xs text-brand-500 hover:text-brand-700 font-semibold transition-colors flex items-center gap-1"
                disabled={fileLoading || ocrLoading}
                onClick={() => fileRef.current?.click()}
              >
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" /></svg>
                {ocrLoading ? "OCR 识别中..." : fileLoading ? "解析文件中..." : "上传文件"}
              </button>
              <input
                ref={fileRef}
                type="file"
                accept=".txt,.docx,.md,.pdf"
                className="hidden"
                onChange={handleFile}
              />
            </div>
          </div>
        </div>

        {/* OCR loading indicator */}
        {ocrLoading && (
          <div className="flex items-center gap-3 bg-brand-50 border border-brand-100 rounded-2xl px-5 py-4">
            <svg className="animate-spin h-5 w-5 text-brand-500 shrink-0" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
            <div>
              <p className="text-sm font-semibold text-brand-800">OCR 识别中...</p>
              <p className="text-xs text-brand-500">正在使用视觉模型识别 PDF 中的文字，请耐心等待</p>
            </div>
          </div>
        )}

        {/* OCR accuracy info */}
        {ocrAccuracy && (
          <div className="flex items-center gap-3 bg-emerald-50 border border-emerald-100 rounded-2xl px-5 py-4">
            <div className="flex-shrink-0 w-9 h-9 rounded-xl bg-emerald-100 flex items-center justify-center">
              <span className="text-sm font-bold text-emerald-700">
                {Math.round(ocrAccuracy.estimate * 100)}
              </span>
            </div>
            <div>
              <p className="text-sm font-semibold text-emerald-800">
                OCR 识别完成 — 预估准确率 {(ocrAccuracy.estimate * 100).toFixed(0)}%
              </p>
              <p className="text-xs text-emerald-500">{ocrAccuracy.note}</p>
            </div>
            <button
              type="button"
              className="ml-auto text-xs text-emerald-400 hover:text-emerald-600 font-semibold transition-colors"
              onClick={() => setOcrAccuracy(null)}
            >
              关闭
            </button>
          </div>
        )}

        {/* Options row */}
        <div className="grid grid-cols-3 gap-4">
          {/* Granularity */}
          <div>
            <label className="label">
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
            <label className="label">
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
            <label className="label">
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
            disabled={loading || ocrLoading || !text.trim() || text.length < MIN_TEXT_LENGTH}
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
        <div className="bg-red-50 border border-red-100 text-red-600 px-5 py-3.5 rounded-2xl text-sm flex items-center gap-2.5">
          <svg className="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" /></svg>
          {error}
        </div>
      )}

      {/* Results */}
      {result && (
        <div className="card space-y-6">
          <h3 className="text-lg font-bold text-gray-900 tracking-tight">检测结果</h3>

          {/* PRIMARY INDICATOR: NHPR */}
          <div className="bg-gradient-to-br from-brand-50 via-purple-50/50 to-brand-50 border border-brand-100 rounded-2xl p-6">
            <div className="flex items-center gap-2 mb-4">
              <div className="w-1.5 h-1.5 rounded-full bg-brand-500"></div>
              <h4 className="text-xs font-bold text-brand-600 uppercase tracking-wider">主要检测指标</h4>
            </div>
            <div className="flex items-center justify-between">
              <div>
                <p className="text-4xl font-extrabold text-gray-900 tracking-tight">
                  {result.nhpr_score !== undefined ? (result.nhpr_score * 100).toFixed(1) : "N/A"}
                  <span className="text-lg font-normal text-gray-300 ml-0.5">%</span>
                </p>
                <p className="text-sm font-semibold text-brand-700 mt-1.5">AI 特征占比 (NHPR)</p>
                <p className="text-xs text-gray-400 mt-1">文本中检测到具有 AI 生成特征的片段比例</p>
              </div>
              <div className="text-right">
                <RiskBadge level={result.nhpr_level ?? result.risk_level ?? "low"} size="lg" />
              </div>
            </div>
          </div>

          {/* SECONDARY REFERENCE: AI Similarity & other metrics */}
          <div className="bg-gray-50/80 rounded-2xl p-5 border border-gray-100">
            <div className="flex items-center gap-2 mb-4">
              <div className="w-1.5 h-1.5 rounded-full bg-gray-300"></div>
              <h4 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest">辅助参考指标</h4>
              <span className="badge-gray text-[10px] ml-auto">仅供参考</span>
            </div>
            <div className="grid grid-cols-3 gap-4">
              <div className="text-center bg-white rounded-xl p-3 border border-gray-100">
                <p className="text-xl font-bold text-gray-700 tracking-tight">
                  {result.risk_score !== undefined ? (result.risk_score * 100).toFixed(1) : "N/A"}
                  <span className="text-[10px] font-medium text-gray-300 ml-0.5">%</span>
                </p>
                <p className="text-[11px] text-gray-400 mt-1 font-medium">AI 相似度</p>
              </div>
              <div className="text-center bg-white rounded-xl p-3 border border-gray-100">
                <p className="text-xl font-bold text-gray-700 tracking-tight">
                  {result.llm_confidence !== undefined ? (result.llm_confidence * 100).toFixed(1) : "N/A"}
                  <span className="text-[10px] font-medium text-gray-300 ml-0.5">%</span>
                </p>
                <p className="text-[11px] text-gray-400 mt-1 font-medium">LLM 置信度</p>
              </div>
              <div className="text-center bg-white rounded-xl p-3 border border-gray-100">
                <p className="text-xl font-bold text-gray-700 tracking-tight">
                  {result.statistical_score !== undefined ? (result.statistical_score * 100).toFixed(1) : "N/A"}
                  <span className="text-[10px] font-medium text-gray-300 ml-0.5">%</span>
                </p>
                <p className="text-[11px] text-gray-400 mt-1 font-medium">统计特征</p>
              </div>
            </div>
            <p className="text-[11px] text-gray-400 mt-4 leading-relaxed">
              AI 相似度为辅助参考指标，基于大语言模型概率估计，存在固有不确定性，不可作为单一判定依据。
            </p>
          </div>

          {/* Evidence completeness (compact) */}
          {result.evidence_completeness !== undefined && (
            <div className="flex items-center gap-3 text-xs text-gray-500">
              <span>证据完备度：{(result.evidence_completeness * 100).toFixed(0)}%</span>
              <div className="flex-1 bg-gray-200 rounded-full h-1.5">
                <div
                  className="bg-brand-500 h-1.5 rounded-full transition-all"
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

          {/* Highlighted Text — show flagged AI segments */}
          {result.flagged_segments && result.flagged_segments.length > 0 && (
            <HighlightedText text={text} segments={result.flagged_segments} />
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
            <div className="bg-amber-50 border border-amber-100 rounded-2xl p-4 text-xs text-amber-700">
              <span className="font-bold">不确定性声明：</span>
              {result.uncertainty_note}
            </div>
          )}

          {/* Actions */}
          <div className="flex items-center gap-3 pt-2 border-t border-gray-100">
            <button
              className="btn-primary flex items-center gap-1.5"
              onClick={() => navigate("/detect/report")}
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/></svg>
              检测报告
            </button>
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
            <div className="border border-gray-100 rounded-2xl p-5 space-y-4 bg-gray-50/50">
              <p className="text-sm font-bold text-gray-700">检测结果反馈</p>
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
