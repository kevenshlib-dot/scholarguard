import { useState } from "react";
import { searchLiterature } from "../../services/api";
import type { LiteratureItem } from "../../services/api";

export default function ResearchPage() {
  const [query, setQuery] = useState("");
  const [topK, setTopK] = useState(5);
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<LiteratureItem[]>([]);
  const [error, setError] = useState("");
  const [expandedIdx, setExpandedIdx] = useState<number | null>(null);

  const handleSearch = async () => {
    if (!query.trim()) return;
    setLoading(true);
    setError("");
    setResults([]);
    try {
      const res = await searchLiterature(query, topK);
      setResults(res.results);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "搜索失败");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto px-6 py-8 space-y-6">
      {/* Demo banner */}
      <div className="bg-yellow-50 border border-yellow-200 rounded-lg px-4 py-3 flex items-center gap-2">
        <span className="text-lg">🟡</span>
        <span className="text-sm font-medium text-yellow-800">
          文献研究 - Demo版
        </span>
        <span className="text-xs text-yellow-600 ml-1">
          部分功能受限，仅供体验
        </span>
      </div>

      <div>
        <h2 className="text-2xl font-bold text-gray-900">文献研究</h2>
        <p className="text-sm text-gray-500 mt-1">
          语义搜索相关文献，辅助学术写作
        </p>
      </div>

      {/* Search */}
      <div className="card space-y-4">
        <div className="flex gap-3">
          <input
            className="input flex-1"
            placeholder="输入研究主题或关键词..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSearch()}
          />
          <div className="flex items-center gap-2">
            <label className="text-xs text-gray-500 whitespace-nowrap">
              返回数量
            </label>
            <select
              className="select w-20"
              value={topK}
              onChange={(e) => setTopK(Number(e.target.value))}
            >
              {[3, 5, 10, 20].map((n) => (
                <option key={n} value={n}>
                  {n}
                </option>
              ))}
            </select>
          </div>
          <button
            className="btn-primary whitespace-nowrap"
            disabled={loading || !query.trim()}
            onClick={handleSearch}
          >
            {loading ? "搜索中..." : "搜索文献"}
          </button>
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
        <div className="space-y-3">
          <p className="text-sm text-gray-500">
            找到 {results.length} 篇相关文献
          </p>
          {results.map((item, i) => (
            <div key={i} className="card space-y-2">
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1 min-w-0">
                  <h4 className="text-sm font-semibold text-gray-900">
                    {item.title}
                  </h4>
                  <p className="text-xs text-gray-500 mt-0.5">
                    {item.authors.join(", ")} &middot; {item.year} &middot;{" "}
                    {item.source}
                  </p>
                </div>
                <button
                  className="text-xs text-brand-600 hover:text-brand-700 font-medium whitespace-nowrap"
                  onClick={() =>
                    setExpandedIdx(expandedIdx === i ? null : i)
                  }
                >
                  {expandedIdx === i ? "收起" : "摘要"}
                </button>
              </div>
              {expandedIdx === i && (
                <div className="bg-gray-50 rounded-lg p-3 text-sm text-gray-600 leading-relaxed">
                  {item.abstract}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
