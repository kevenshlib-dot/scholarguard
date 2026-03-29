import { useState } from "react";
import type { FlaggedSegment } from "../services/api";

interface Props {
  text: string;
  segments: FlaggedSegment[];
}

/**
 * Renders the original text with flagged (AI-suspected) segments highlighted.
 *
 * Segments are matched by text_snippet (fuzzy substring search) since
 * start_char/end_char from the LLM may not align perfectly with the
 * full input text (which may have been truncated for the LLM).
 */
export default function HighlightedText({ text, segments }: Props) {
  const [activeIdx, setActiveIdx] = useState<number | null>(null);

  if (!segments.length) return null;

  // Build highlight ranges by matching snippets in the full text
  const ranges: { start: number; end: number; issue: string; idx: number }[] = [];

  segments.forEach((seg, idx) => {
    const snippet = seg.text_snippet?.trim();
    if (!snippet) return;

    // Try exact start_char/end_char first
    if (
      seg.start_char > 0 &&
      seg.end_char > seg.start_char &&
      seg.end_char <= text.length
    ) {
      const slice = text.slice(seg.start_char, seg.end_char);
      // Accept if >=60% of the snippet matches
      if (slice.includes(snippet.slice(0, 20)) || snippet.includes(slice.slice(0, 20))) {
        ranges.push({ start: seg.start_char, end: seg.end_char, issue: seg.issue, idx });
        return;
      }
    }

    // Fallback: search for the snippet as a substring
    const pos = text.indexOf(snippet);
    if (pos !== -1) {
      ranges.push({ start: pos, end: pos + snippet.length, issue: seg.issue, idx });
      return;
    }

    // Fuzzy: try first 30 chars of the snippet
    const partial = snippet.slice(0, 30);
    const ppos = text.indexOf(partial);
    if (ppos !== -1) {
      ranges.push({
        start: ppos,
        end: Math.min(ppos + snippet.length, text.length),
        issue: seg.issue,
        idx,
      });
    }
  });

  // Sort by start position and merge overlaps
  ranges.sort((a, b) => a.start - b.start);
  const merged: typeof ranges = [];
  for (const r of ranges) {
    const last = merged[merged.length - 1];
    if (last && r.start <= last.end) {
      last.end = Math.max(last.end, r.end);
      last.issue = last.issue + "; " + r.issue;
    } else {
      merged.push({ ...r });
    }
  }

  if (!merged.length) {
    // No matches found — show snippet list as fallback
    return (
      <div className="space-y-3">
        <h4 className="text-sm font-semibold text-gray-700">
          疑似 AI 生成片段
          <span className="ml-2 text-xs font-normal text-gray-400">
            ({segments.length} 处标记)
          </span>
        </h4>
        <div className="space-y-2">
          {segments.map((seg, i) => (
            <div
              key={i}
              className="bg-red-50 border-l-4 border-red-400 px-3 py-2 rounded-r-lg"
            >
              <p className="text-sm text-gray-800">
                &ldquo;{seg.text_snippet}&rdquo;
              </p>
              {seg.issue && (
                <p className="text-xs text-red-600 mt-1">{seg.issue}</p>
              )}
            </div>
          ))}
        </div>
      </div>
    );
  }

  // Build rendered fragments
  const fragments: JSX.Element[] = [];
  let cursor = 0;

  merged.forEach((r, i) => {
    // Plain text before this range
    if (cursor < r.start) {
      fragments.push(
        <span key={`t${i}`}>{text.slice(cursor, r.start)}</span>
      );
    }

    // Highlighted segment
    const isActive = activeIdx === i;
    fragments.push(
      <span
        key={`h${i}`}
        className={`relative cursor-pointer rounded px-0.5 transition-colors ${
          isActive
            ? "bg-red-300/60 ring-2 ring-red-400"
            : "bg-red-200/50 hover:bg-red-300/50"
        }`}
        onMouseEnter={() => setActiveIdx(i)}
        onMouseLeave={() => setActiveIdx(null)}
      >
        {text.slice(r.start, r.end)}
        {/* Tooltip */}
        {isActive && r.issue && (
          <span className="absolute left-0 bottom-full mb-1 z-20 w-72 bg-gray-900 text-white text-xs rounded-lg px-3 py-2 shadow-lg pointer-events-none whitespace-normal">
            {r.issue}
          </span>
        )}
      </span>
    );

    cursor = r.end;
  });

  // Trailing plain text
  if (cursor < text.length) {
    fragments.push(<span key="tail">{text.slice(cursor)}</span>);
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-3">
        <h4 className="text-sm font-semibold text-gray-700">
          文本高亮分析
        </h4>
        <span className="inline-flex items-center gap-1.5 text-xs text-gray-500">
          <span className="inline-block w-3 h-3 rounded bg-red-200/60" />
          疑似 AI 生成 ({merged.length} 处)
        </span>
        <span className="text-xs text-gray-400">
          悬停高亮区域查看原因
        </span>
      </div>
      <div className="bg-gray-50 rounded-lg p-4 text-sm text-gray-800 leading-relaxed whitespace-pre-wrap max-h-[500px] overflow-y-auto">
        {fragments}
      </div>
    </div>
  );
}
