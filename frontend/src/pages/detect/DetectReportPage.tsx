import { useEffect, useState, useRef } from "react";
import { useNavigate } from "react-router-dom";
import html2canvas from "html2canvas";
import { jsPDF } from "jspdf";
import type { DetectResultData } from "../../services/api";

/* ── Helpers ─────────────────────────────────────────────── */

const riskConfig: Record<string, { label: string; color: string; bg: string }> = {
  low:      { label: "低风险",   color: "#15803d", bg: "#dcfce7" },
  medium:   { label: "中等风险", color: "#a16207", bg: "#fef9c3" },
  high:     { label: "高风险",   color: "#dc2626", bg: "#fee2e2" },
  critical: { label: "极高风险", color: "#7e22ce", bg: "#f3e8ff" },
  unknown:  { label: "检测失败", color: "#6b7280", bg: "#f3f4f6" },
  error:    { label: "检测失败", color: "#6b7280", bg: "#f3f4f6" },
};

function pct(v?: number): string {
  return v !== undefined ? `${(v * 100).toFixed(1)}%` : "N/A";
}

function riskLabel(level?: string) {
  return riskConfig[level ?? "low"]?.label ?? level ?? "未知";
}

function riskColor(level?: string) {
  return riskConfig[level ?? "low"] ?? riskConfig.low;
}

function granularityLabel(g?: string) {
  const map: Record<string, string> = { document: "整篇文档", paragraph: "段落级别", sentence: "句子级别" };
  return map[g ?? ""] ?? g ?? "文档级";
}

function languageLabel(l?: string) {
  const map: Record<string, string> = { auto: "自动检测", zh: "中文", en: "英文" };
  return map[l ?? ""] ?? l ?? "自动";
}

function disciplineLabel(d?: string) {
  const map: Record<string, string> = {
    general: "通用", politics: "政治学", economics: "经济学",
    sociology: "社会学", law: "法学",
  };
  return map[d ?? ""] ?? d ?? "通用";
}

/**
 * Extract title, author, and abstract from academic text.
 * Heuristic: first non-empty line → title; lines containing author keywords → author;
 * text after "摘要"/"Abstract" keyword → abstract; fallback to first ~300 chars.
 */
function extractAbstract(fullText: string): { title: string; author: string; abstract: string } {
  const lines = fullText.split(/\n/).map((l) => l.trim()).filter(Boolean);
  if (!lines.length) return { title: "（未提供）", author: "（未提供）", abstract: "（未提供）" };

  // Title: first line (often the title in academic papers)
  const title = lines[0].length > 200 ? lines[0].slice(0, 200) + "..." : lines[0];

  // Author: look for lines with author-like keywords near the top (first 10 lines)
  let author = "";
  const authorPatterns = /^(作者|作　者|Author|Authors|By)\s*[:：]?\s*/i;
  const topLines = lines.slice(1, 15);
  for (const line of topLines) {
    if (authorPatterns.test(line)) {
      author = line.replace(authorPatterns, "").trim();
      break;
    }
  }
  // Fallback: second line if it looks like names (short, no period ending)
  if (!author && lines.length > 1) {
    const candidate = lines[1];
    if (candidate.length < 100 && !candidate.endsWith("。") && !candidate.endsWith(".")) {
      author = candidate;
    }
  }

  // Abstract: find "摘要" or "Abstract" section
  let abstract = "";
  const fullJoined = fullText;
  // Chinese abstract
  const zhMatch = fullJoined.match(/摘\s*要\s*[:：]?\s*([\s\S]{10,800}?)(?=\n\s*关键词|关\s*键\s*词|\n\s*Keywords|\n\s*1[\s.、]|\n\s*一[\s、.]|$)/i);
  if (zhMatch) {
    abstract = zhMatch[1].trim().replace(/\s+/g, " ");
  }
  // English abstract
  if (!abstract) {
    const enMatch = fullJoined.match(/Abstract\s*[:：]?\s*([\s\S]{10,800}?)(?=\n\s*Keywords|\n\s*1[\s.]|\n\s*Introduction|$)/i);
    if (enMatch) {
      abstract = enMatch[1].trim().replace(/\s+/g, " ");
    }
  }
  // Fallback: first 300 chars as summary
  if (!abstract) {
    const fallback = lines.slice(0, 8).join(" ").trim();
    abstract = fallback.length > 300 ? fallback.slice(0, 300) + "..." : fallback;
  }
  if (abstract.length > 500) {
    abstract = abstract.slice(0, 500) + "...";
  }

  return { title, author: author || "（未提供）", abstract };
}

function scoreBarColor(score: number): string {
  if (score < 0.3) return "#22c55e";
  if (score < 0.5) return "#eab308";
  if (score < 0.7) return "#f97316";
  if (score < 0.85) return "#ef4444";
  return "#a855f7";
}

/* ── Main Component ──────────────────────────────────────── */

export default function DetectReportPage() {
  const navigate = useNavigate();
  const printRef = useRef<HTMLDivElement>(null);
  const [result, setResult] = useState<DetectResultData | null>(null);
  const [text, setText] = useState("");
  const [params, setParams] = useState<{
    granularity?: string; language?: string; discipline?: string;
  }>({});
  const [downloading, setDownloading] = useState(false);

  useEffect(() => {
    const raw = sessionStorage.getItem("sg_detect_result");
    const t = sessionStorage.getItem("sg_detect_text") || "";
    const p = sessionStorage.getItem("sg_detect_params");
    if (!raw) {
      navigate("/detect");
      return;
    }
    try {
      setResult(JSON.parse(raw));
    } catch {
      navigate("/detect");
      return;
    }
    setText(t);
    if (p) {
      try { setParams(JSON.parse(p)); } catch { /* ignore */ }
    }
  }, [navigate]);

  if (!result) return null;

  const rc = riskColor(result.risk_level);
  const now = new Date();
  const reportTime = now.toLocaleString("zh-CN", {
    year: "numeric", month: "2-digit", day: "2-digit",
    hour: "2-digit", minute: "2-digit", second: "2-digit",
  });
  const reportId = `SG-${now.getFullYear()}${String(now.getMonth()+1).padStart(2,"0")}${String(now.getDate()).padStart(2,"0")}-${result.task_id?.slice(0, 8).toUpperCase() ?? "UNKNOWN"}`;

  /* ---- Download as PDF ---- */
  const handleDownload = async () => {
    const el = printRef.current;
    if (!el || downloading) return;

    setDownloading(true);
    try {
      // Render the report element to a high-resolution canvas
      const canvas = await html2canvas(el, {
        scale: 2, // 2x for crisp text
        useCORS: true,
        logging: false,
        backgroundColor: "#ffffff",
        windowWidth: 800,
      });

      const imgWidth = 210; // A4 width in mm
      const pageHeight = 297; // A4 height in mm
      const imgHeight = (canvas.height * imgWidth) / canvas.width;
      const imgData = canvas.toDataURL("image/png");

      const pdf = new jsPDF("p", "mm", "a4");
      let heightLeft = imgHeight;
      let position = 0;

      // First page
      pdf.addImage(imgData, "PNG", 0, position, imgWidth, imgHeight);
      heightLeft -= pageHeight;

      // Additional pages if content overflows
      while (heightLeft > 0) {
        position -= pageHeight;
        pdf.addPage();
        pdf.addImage(imgData, "PNG", 0, position, imgWidth, imgHeight);
        heightLeft -= pageHeight;
      }

      pdf.save(`ScholarGuard_检测报告_${reportId}.pdf`);
    } catch (err) {
      console.error("PDF generation failed:", err);
      alert("PDF 生成失败，请尝试使用打印功能另存为 PDF");
    } finally {
      setDownloading(false);
    }
  };

  /* ---- Print ---- */
  const handlePrint = () => {
    window.print();
  };

  return (
    <div className="min-h-screen bg-gray-100">
      {/* Toolbar — hidden in print */}
      <div className="print:hidden sticky top-0 z-10 bg-white border-b border-gray-200 shadow-sm">
        <div className="max-w-[860px] mx-auto px-6 py-3 flex items-center justify-between">
          <button
            onClick={() => navigate("/detect")}
            className="text-sm text-gray-600 hover:text-gray-900 flex items-center gap-1.5"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7"/></svg>
            返回检测页
          </button>
          <div className="flex items-center gap-3">
            <button onClick={handlePrint} className="btn-secondary text-sm flex items-center gap-1.5">
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 17h2a2 2 0 002-2v-4a2 2 0 00-2-2H5a2 2 0 00-2 2v4a2 2 0 002 2h2m2 4h6a2 2 0 002-2v-4a2 2 0 00-2-2H9a2 2 0 00-2 2v4a2 2 0 002 2zm8-12V5a2 2 0 00-2-2H9a2 2 0 00-2 2v4h10z"/></svg>
              打印
            </button>
            <button onClick={handleDownload} disabled={downloading} className="btn-primary text-sm flex items-center gap-1.5 disabled:opacity-60">
              {downloading ? (
                <>
                  <svg className="animate-spin w-4 h-4" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none"/><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/></svg>
                  生成 PDF 中...
                </>
              ) : (
                <>
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/></svg>
                  下载 PDF
                </>
              )}
            </button>
          </div>
        </div>
      </div>

      {/* Report Content */}
      <div ref={printRef} className="report max-w-[800px] mx-auto bg-white my-6 print:my-0 shadow-lg print:shadow-none rounded-lg print:rounded-none">
        <div style={{ maxWidth: 800, margin: "0 auto", padding: "40px 50px" }}>
          {/* ── Header ── */}
          <div style={{ textAlign: "center", borderBottom: "3px solid #4f46e5", paddingBottom: 24, marginBottom: 32 }}>
            <div style={{ fontSize: 28, fontWeight: 800, color: "#4f46e5", marginBottom: 8 }}>ScholarGuard</div>
            <h1 style={{ fontSize: 24, color: "#1f2937", marginBottom: 4 }}>AI 内容检测报告</h1>
            <div style={{ fontSize: 13, color: "#6b7280" }}>Evidence-Based Academic AI Detection Report</div>
          </div>

          {/* ── Report Meta ── */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px 24px", fontSize: 13, marginBottom: 28, padding: 16, background: "#f9fafb", borderRadius: 8 }}>
            <div><span style={{ color: "#6b7280" }}>报告编号：</span><span style={{ fontWeight: 500 }}>{reportId}</span></div>
            <div><span style={{ color: "#6b7280" }}>生成时间：</span><span style={{ fontWeight: 500 }}>{reportTime}</span></div>
            <div><span style={{ color: "#6b7280" }}>检测任务ID：</span><span style={{ fontWeight: 500 }}>{result.task_id}</span></div>
            <div><span style={{ color: "#6b7280" }}>检测状态：</span><span style={{ fontWeight: 500, color: "#15803d" }}>已完成</span></div>
          </div>

          {/* ── Section 1: Detection Environment ── */}
          <div style={{ marginBottom: 28 }}>
            <h2 style={{ fontSize: 16, fontWeight: 700, borderLeft: "4px solid #4f46e5", paddingLeft: 12, marginBottom: 16 }}>一、检测环境</h2>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px 24px", fontSize: 13, padding: 16, background: "#f9fafb", borderRadius: 8 }}>
              <div><span style={{ color: "#6b7280" }}>检测平台：</span><span style={{ fontWeight: 500 }}>ScholarGuard v1.0</span></div>
              <div><span style={{ color: "#6b7280" }}>检测引擎：</span><span style={{ fontWeight: 500 }}>LLM-Center (Qwen3.5-27B)</span></div>
              <div><span style={{ color: "#6b7280" }}>检测粒度：</span><span style={{ fontWeight: 500 }}>{granularityLabel(params.granularity)}</span></div>
              <div><span style={{ color: "#6b7280" }}>文本语言：</span><span style={{ fontWeight: 500 }}>{languageLabel(params.language)}</span></div>
              <div><span style={{ color: "#6b7280" }}>学科领域：</span><span style={{ fontWeight: 500 }}>{disciplineLabel(params.discipline)}</span></div>
              <div><span style={{ color: "#6b7280" }}>文本长度：</span><span style={{ fontWeight: 500 }}>{text.length.toLocaleString()} 字符</span></div>
            </div>
          </div>

          {/* ── Section 2: Overall Conclusion ── */}
          <div style={{ marginBottom: 28 }}>
            <h2 style={{ fontSize: 16, fontWeight: 700, borderLeft: "4px solid #4f46e5", paddingLeft: 12, marginBottom: 16 }}>二、检测结论</h2>

            {/* Risk Banner */}
            <div style={{
              display: "flex", alignItems: "center", justifyContent: "center", gap: 16,
              padding: 20, borderRadius: 12, background: rc.bg, marginBottom: 20,
            }}>
              <div style={{ fontSize: 22, fontWeight: 800, color: rc.color }}>
                {riskLabel(result.risk_level)}
              </div>
              <div style={{ fontSize: 36, fontWeight: 800, color: rc.color }}>
                {pct(result.risk_score)}
              </div>
            </div>

            {/* Metric Cards */}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 12, marginBottom: 20 }}>
              <div style={{ textAlign: "center", padding: 14, background: "#f9fafb", borderRadius: 8, border: "1px solid #e5e7eb" }}>
                <div style={{ fontSize: 22, fontWeight: 700 }}>{pct(result.llm_confidence)}</div>
                <div style={{ fontSize: 12, color: "#6b7280", marginTop: 2 }}>LLM 置信度</div>
              </div>
              <div style={{ textAlign: "center", padding: 14, background: "#f9fafb", borderRadius: 8, border: "1px solid #e5e7eb" }}>
                <div style={{ fontSize: 22, fontWeight: 700 }}>{pct(result.statistical_score)}</div>
                <div style={{ fontSize: 12, color: "#6b7280", marginTop: 2 }}>统计特征分数</div>
              </div>
              <div style={{ textAlign: "center", padding: 14, background: "#f9fafb", borderRadius: 8, border: "1px solid #e5e7eb" }}>
                <div style={{ fontSize: 22, fontWeight: 700 }}>{pct(result.evidence_completeness)}</div>
                <div style={{ fontSize: 12, color: "#6b7280", marginTop: 2 }}>证据完备度</div>
              </div>
            </div>

            {/* Evidence Completeness Bar */}
            {result.evidence_completeness !== undefined && (
              <div style={{ marginBottom: 8 }}>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, color: "#6b7280", marginBottom: 4 }}>
                  <span>证据完备度</span>
                  <span>{pct(result.evidence_completeness)}</span>
                </div>
                <div style={{ height: 10, background: "#e5e7eb", borderRadius: 5, overflow: "hidden" }}>
                  <div style={{ height: "100%", width: pct(result.evidence_completeness), borderRadius: 5, background: "#4f46e5" }} />
                </div>
              </div>
            )}
          </div>

          {/* ── Section 3: Paragraph Heatmap ── */}
          {result.paragraph_scores && result.paragraph_scores.length > 0 && (
            <div style={{ marginBottom: 28 }}>
              <h2 style={{ fontSize: 16, fontWeight: 700, borderLeft: "4px solid #4f46e5", paddingLeft: 12, marginBottom: 16 }}>三、段落风险热力图</h2>
              <div style={{ display: "flex", gap: 3 }}>
                {result.paragraph_scores.map((p) => (
                  <div key={p.index} style={{
                    flex: 1, height: 36, borderRadius: 4,
                    display: "flex", alignItems: "center", justifyContent: "center",
                    color: "#fff", fontSize: 11, fontWeight: 700,
                    background: scoreBarColor(p.score),
                  }}>
                    {p.index + 1}
                  </div>
                ))}
              </div>
              {/* Legend */}
              <div style={{ display: "flex", gap: 12, justifyContent: "center", marginTop: 8, fontSize: 11, color: "#6b7280" }}>
                <span><span style={{ display: "inline-block", width: 10, height: 10, borderRadius: 2, background: "#22c55e", marginRight: 3, verticalAlign: "middle" }}/>低</span>
                <span><span style={{ display: "inline-block", width: 10, height: 10, borderRadius: 2, background: "#eab308", marginRight: 3, verticalAlign: "middle" }}/>中</span>
                <span><span style={{ display: "inline-block", width: 10, height: 10, borderRadius: 2, background: "#f97316", marginRight: 3, verticalAlign: "middle" }}/>偏高</span>
                <span><span style={{ display: "inline-block", width: 10, height: 10, borderRadius: 2, background: "#ef4444", marginRight: 3, verticalAlign: "middle" }}/>高</span>
                <span><span style={{ display: "inline-block", width: 10, height: 10, borderRadius: 2, background: "#a855f7", marginRight: 3, verticalAlign: "middle" }}/>极高</span>
              </div>

              {/* Paragraph detail table */}
              <table style={{ width: "100%", fontSize: 12, marginTop: 12, borderCollapse: "collapse" }}>
                <thead>
                  <tr style={{ borderBottom: "2px solid #e5e7eb" }}>
                    <th style={{ padding: "8px 6px", textAlign: "left", color: "#6b7280", fontWeight: 600 }}>段落</th>
                    <th style={{ padding: "8px 6px", textAlign: "center", color: "#6b7280", fontWeight: 600 }}>风险评分</th>
                    <th style={{ padding: "8px 6px", textAlign: "left", color: "#6b7280", fontWeight: 600 }}>内容预览</th>
                  </tr>
                </thead>
                <tbody>
                  {result.paragraph_scores.map((p) => (
                    <tr key={p.index} style={{ borderBottom: "1px solid #f3f4f6" }}>
                      <td style={{ padding: "8px 6px", fontWeight: 600 }}>P{p.index + 1}</td>
                      <td style={{ padding: "8px 6px", textAlign: "center" }}>
                        <span style={{ padding: "2px 8px", borderRadius: 9999, fontSize: 11, fontWeight: 600, background: scoreBarColor(p.score), color: "#fff" }}>
                          {(p.score * 100).toFixed(0)}%
                        </span>
                      </td>
                      <td style={{ padding: "8px 6px", color: "#4b5563", maxWidth: 400, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                        {p.text.length > 80 ? p.text.slice(0, 80) + "..." : p.text}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* ── Section 4: Flagged Segments ── */}
          {result.flagged_segments && result.flagged_segments.length > 0 && (
            <div style={{ marginBottom: 28 }}>
              <h2 style={{ fontSize: 16, fontWeight: 700, borderLeft: "4px solid #4f46e5", paddingLeft: 12, marginBottom: 16 }}>
                {result.paragraph_scores?.length ? "四" : "三"}、疑似 AI 生成片段（{result.flagged_segments.length} 处）
              </h2>
              {result.flagged_segments.map((seg, i) => (
                <div key={i} style={{ padding: "10px 14px", marginBottom: 8, borderLeft: "4px solid #ef4444", background: "#fef2f2", borderRadius: "0 8px 8px 0" }}>
                  <div style={{ fontSize: 13, color: "#1f2937" }}>"{seg.text_snippet}"</div>
                  {seg.issue && <div style={{ fontSize: 12, color: "#dc2626", marginTop: 4 }}>{seg.issue}</div>}
                </div>
              ))}
            </div>
          )}

          {/* ── Section 5: Evidence Summary ── */}
          {result.evidence_summary && (
            <div style={{ marginBottom: 28 }}>
              <h2 style={{ fontSize: 16, fontWeight: 700, borderLeft: "4px solid #4f46e5", paddingLeft: 12, marginBottom: 16 }}>
                {(() => {
                  let n = 3;
                  if (result.paragraph_scores?.length) n++;
                  if (result.flagged_segments?.length) n++;
                  const nums = ["三","四","五","六","七"];
                  return nums[n-3] ?? String(n);
                })()}、证据分析
              </h2>
              <div style={{ fontSize: 13, lineHeight: 1.8, padding: 16, background: "#f9fafb", borderRadius: 8, color: "#374151" }}>
                {result.evidence_summary}
              </div>
            </div>
          )}

          {/* ── Section: Recommendations ── */}
          {result.recommendations && result.recommendations.length > 0 && (
            <div style={{ marginBottom: 28 }}>
              <h2 style={{ fontSize: 16, fontWeight: 700, borderLeft: "4px solid #4f46e5", paddingLeft: 12, marginBottom: 16 }}>建议措施</h2>
              <ul style={{ listStyle: "none", padding: 0 }}>
                {result.recommendations.map((rec, i) => (
                  <li key={i} style={{ fontSize: 13, padding: "6px 0", paddingLeft: 16, position: "relative", color: "#374151" }}>
                    <span style={{ position: "absolute", left: 0, color: "#4f46e5", fontWeight: "bold" }}>•</span>
                    {rec}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* ── Section: Paper Abstract Info ── */}
          {(() => {
            const info = extractAbstract(text);
            return (
              <div style={{ marginBottom: 28 }}>
                <h2 style={{ fontSize: 16, fontWeight: 700, borderLeft: "4px solid #4f46e5", paddingLeft: 12, marginBottom: 16 }}>附录：受检论文信息</h2>
                <div style={{ padding: 16, background: "#f9fafb", borderRadius: 8 }}>
                  <table style={{ width: "100%", fontSize: 13, borderCollapse: "collapse" }}>
                    <tbody>
                      <tr style={{ borderBottom: "1px solid #e5e7eb" }}>
                        <td style={{ padding: "10px 12px", color: "#6b7280", fontWeight: 600, whiteSpace: "nowrap", verticalAlign: "top", width: 80 }}>标题</td>
                        <td style={{ padding: "10px 12px", color: "#1f2937", fontWeight: 500 }}>{info.title}</td>
                      </tr>
                      <tr style={{ borderBottom: "1px solid #e5e7eb" }}>
                        <td style={{ padding: "10px 12px", color: "#6b7280", fontWeight: 600, whiteSpace: "nowrap", verticalAlign: "top" }}>作者</td>
                        <td style={{ padding: "10px 12px", color: "#1f2937" }}>{info.author}</td>
                      </tr>
                      <tr style={{ borderBottom: "1px solid #e5e7eb" }}>
                        <td style={{ padding: "10px 12px", color: "#6b7280", fontWeight: 600, whiteSpace: "nowrap", verticalAlign: "top" }}>字数</td>
                        <td style={{ padding: "10px 12px", color: "#1f2937" }}>{text.length.toLocaleString()} 字符</td>
                      </tr>
                      <tr>
                        <td style={{ padding: "10px 12px", color: "#6b7280", fontWeight: 600, whiteSpace: "nowrap", verticalAlign: "top" }}>摘要</td>
                        <td style={{ padding: "10px 12px", color: "#374151", lineHeight: 1.8 }}>{info.abstract}</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>
            );
          })()}

          {/* ── Uncertainty Disclaimer ── */}
          {result.uncertainty_note && (
            <div style={{ fontSize: 12, color: "#92400e", background: "#fffbeb", border: "1px solid #fde68a", padding: "12px 16px", borderRadius: 8, marginBottom: 20 }}>
              <strong>不确定性声明：</strong>{result.uncertainty_note}
            </div>
          )}

          <div style={{ fontSize: 12, color: "#92400e", background: "#fffbeb", border: "1px solid #fde68a", padding: "12px 16px", borderRadius: 8, marginBottom: 20 }}>
            <strong>免责声明：</strong>本报告由 ScholarGuard 平台基于大语言模型和统计分析自动生成，检测结果为概率性参考意见，不构成最终学术判定。AI 检测技术存在固有的不确定性，可能产生假阳性或假阴性结果。最终判断权归使用者所有。
          </div>

          {/* ── Footer ── */}
          <div style={{ textAlign: "center", fontSize: 11, color: "#9ca3af", marginTop: 40, paddingTop: 20, borderTop: "1px solid #e5e7eb" }}>
            <div>ScholarGuard — Evidence-Based Academic AI Detection Platform</div>
            <div style={{ marginTop: 4 }}>报告编号：{reportId} | 生成时间：{reportTime}</div>
            <div style={{ marginTop: 4 }}>本报告由系统自动生成，仅供参考</div>
          </div>
        </div>
      </div>
    </div>
  );
}
