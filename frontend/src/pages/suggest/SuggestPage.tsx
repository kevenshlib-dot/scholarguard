import { useState } from "react";
import { getSuggestions } from "../../services/api";
import type { Suggestion } from "../../services/api";

const strategies = [
  { value: "naturalness", label: "表达自然化", desc: "使文本更贴近人类自然写作风格" },
  { value: "argumentation", label: "论证补强", desc: "增强论证逻辑和证据引用" },
  { value: "structure", label: "结构提醒", desc: "优化段落组织和层次关系" },
  { value: "vocabulary", label: "词汇建议", desc: "丰富用词，减少AI常见表达" },
];

export default function SuggestPage() {
  const [text, setText] = useState("");
  const [selected, setSelected] = useState<string[]>(["naturalness", "vocabulary"]);
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<Suggestion[]>([]);
  const [error, setError] = useState("");

  const toggle = (val: string) => {
    setSelected((prev) =>
      prev.includes(val) ? prev.filter((v) => v !== val) : [...prev, val]
    );
  };

  const handleSubmit = async () => {
    if (!text.trim() || selected.length === 0) return;
    setLoading(true);
    setError("");
    setResults([]);
    try {
      const res = await getSuggestions(text, selected);
      setResults(res.suggestions);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "请求失败");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto px-6 py-8 space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-gray-900">写作建议</h2>
        <p className="text-sm text-gray-500 mt-1">
          获取改善文本自然度和学术质量的建议
        </p>
      </div>

      <div className="card space-y-4">
        {/* Editor */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1.5">
            输入文本
          </label>
          <textarea
            className="input min-h-[180px] resize-y"
            placeholder="粘贴您的学术文本..."
            value={text}
            onChange={(e) => setText(e.target.value)}
          />
          <p className="text-xs text-gray-400 mt-1">{text.length} 字符</p>
        </div>

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

        <button
          className="btn-primary"
          disabled={loading || !text.trim() || selected.length === 0}
          onClick={handleSubmit}
        >
          {loading ? "分析中..." : "获取建议"}
        </button>
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
          <h3 className="text-lg font-semibold text-gray-900">
            优化建议
            <span className="text-sm font-normal text-gray-400 ml-2">
              共 {results.length} 条
            </span>
          </h3>

          <div className="space-y-4">
            {results.map((sug, i) => (
              <div
                key={i}
                className="border border-gray-200 rounded-lg overflow-hidden"
              >
                <div className="flex items-center gap-2 px-4 py-2 bg-gray-50 border-b border-gray-100">
                  <span className="text-xs font-medium text-gray-500">
                    策略：{strategies.find((s) => s.value === sug.strategy)?.label ?? sug.strategy}
                  </span>
                </div>
                <div className="p-4 space-y-2">
                  <div>
                    <span className="text-xs text-gray-400">原文</span>
                    <p className="text-sm text-gray-600 bg-red-50 rounded px-3 py-2 mt-1">
                      {sug.original}
                    </p>
                  </div>
                  <div>
                    <span className="text-xs text-gray-400">建议修改</span>
                    <p className="text-sm text-gray-900 bg-green-50 rounded px-3 py-2 mt-1">
                      {sug.suggested}
                    </p>
                  </div>
                  {sug.explanation && (
                    <p className="text-xs text-gray-500 italic">
                      {sug.explanation}
                    </p>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
