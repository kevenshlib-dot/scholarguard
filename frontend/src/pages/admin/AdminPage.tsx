import { useState } from "react";

type Tab = "model" | "formula" | "usage" | "audit";

export default function AdminPage() {
  const [activeTab, setActiveTab] = useState<Tab>("model");

  const tabs: { key: Tab; label: string }[] = [
    { key: "model", label: "模型配置" },
    { key: "formula", label: "公式参数" },
    { key: "usage", label: "使用量统计" },
    { key: "audit", label: "审计日志" },
  ];

  return (
    <div className="max-w-5xl mx-auto px-6 py-8 space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-gray-900">系统管理</h2>
        <p className="text-sm text-gray-500 mt-1">
          管理模型配置、检测参数和系统运行状况
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

      {/* Model Config */}
      {activeTab === "model" && (
        <div className="card space-y-6">
          <h4 className="font-semibold text-gray-900">检测模型配置</h4>
          <div className="grid grid-cols-2 gap-6">
            <div className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">
                  主检测模型
                </label>
                <select className="select">
                  <option>ScholarGuard-Detect-v1</option>
                  <option>ScholarGuard-Detect-v2-beta</option>
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">
                  语义分析模型
                </label>
                <select className="select">
                  <option>BERT-Chinese-WWM</option>
                  <option>RoBERTa-Large-Chinese</option>
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">
                  推理批大小
                </label>
                <input type="number" className="input" defaultValue={32} />
              </div>
            </div>
            <div className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">
                  置信度阈值
                </label>
                <input
                  type="number"
                  className="input"
                  defaultValue={0.7}
                  step={0.05}
                  min={0}
                  max={1}
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">
                  最大文本长度（字符）
                </label>
                <input type="number" className="input" defaultValue={50000} />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">
                  并发任务上限
                </label>
                <input type="number" className="input" defaultValue={10} />
              </div>
            </div>
          </div>
          <button className="btn-primary">保存配置</button>
        </div>
      )}

      {/* Formula Params */}
      {activeTab === "formula" && (
        <div className="card space-y-6">
          <h4 className="font-semibold text-gray-900">综合风险评分公式参数</h4>
          <p className="text-sm text-gray-500">
            Risk = w1*P(model) + w2*P(stat) + w3*P(semantic) - w4*Evidence
          </p>
          <div className="grid grid-cols-4 gap-4">
            {[
              { name: "w1 (模型概率权重)", defaultVal: "0.35" },
              { name: "w2 (统计特征权重)", defaultVal: "0.25" },
              { name: "w3 (语义分析权重)", defaultVal: "0.25" },
              { name: "w4 (证据折减系数)", defaultVal: "0.15" },
            ].map((p) => (
              <div key={p.name}>
                <label className="block text-xs font-medium text-gray-500 mb-1">
                  {p.name}
                </label>
                <input
                  type="number"
                  className="input"
                  defaultValue={p.defaultVal}
                  step={0.05}
                  min={0}
                  max={1}
                />
              </div>
            ))}
          </div>

          <h4 className="font-semibold text-gray-900 pt-4">风险等级阈值</h4>
          <div className="grid grid-cols-4 gap-4">
            {[
              { label: "低风险上限", val: "0.30", color: "text-green-600" },
              { label: "中风险上限", val: "0.55", color: "text-yellow-600" },
              { label: "高风险上限", val: "0.80", color: "text-red-600" },
              { label: "极高风险阈值", val: "0.80", color: "text-purple-600" },
            ].map((t) => (
              <div key={t.label}>
                <label className={`block text-xs font-medium mb-1 ${t.color}`}>
                  {t.label}
                </label>
                <input
                  type="number"
                  className="input"
                  defaultValue={t.val}
                  step={0.05}
                  min={0}
                  max={1}
                />
              </div>
            ))}
          </div>
          <button className="btn-primary">保存参数</button>
        </div>
      )}

      {/* Usage Stats */}
      {activeTab === "usage" && (
        <div className="space-y-4">
          <div className="grid grid-cols-4 gap-4">
            {[
              { label: "今日检测量", value: "342", trend: "+12%" },
              { label: "本月检测量", value: "8,291", trend: "+8%" },
              { label: "平均响应时间", value: "2.3s", trend: "-15%" },
              { label: "系统可用率", value: "99.7%", trend: "" },
            ].map((s) => (
              <div key={s.label} className="card text-center">
                <p className="text-2xl font-bold text-gray-900">{s.value}</p>
                <p className="text-xs text-gray-500 mt-1">{s.label}</p>
                {s.trend && (
                  <p
                    className={`text-xs mt-1 font-medium ${
                      s.trend.startsWith("+") ? "text-green-600" : "text-blue-600"
                    }`}
                  >
                    {s.trend}
                  </p>
                )}
              </div>
            ))}
          </div>

          <div className="card">
            <h4 className="font-semibold text-gray-900 mb-4">检测量趋势</h4>
            <div className="h-48 bg-gray-50 rounded-lg flex items-center justify-center text-sm text-gray-400">
              图表区域 - 集成 Plotly 后展示检测量趋势折线图
            </div>
          </div>
        </div>
      )}

      {/* Audit Logs */}
      {activeTab === "audit" && (
        <div className="card">
          <h4 className="font-semibold text-gray-900 mb-4">审计日志</h4>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200 text-left">
                  <th className="pb-2 text-xs font-medium text-gray-500">时间</th>
                  <th className="pb-2 text-xs font-medium text-gray-500">操作</th>
                  <th className="pb-2 text-xs font-medium text-gray-500">用户</th>
                  <th className="pb-2 text-xs font-medium text-gray-500">详情</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {[
                  {
                    time: "2026-03-29 10:23",
                    action: "检测提交",
                    user: "user_001",
                    detail: "提交文档检测，3,200字",
                  },
                  {
                    time: "2026-03-29 09:15",
                    action: "参数修改",
                    user: "admin",
                    detail: "修改w1权重: 0.30 → 0.35",
                  },
                  {
                    time: "2026-03-28 16:45",
                    action: "复核完成",
                    user: "reviewer_02",
                    detail: "维持判定 det-003",
                  },
                  {
                    time: "2026-03-28 14:00",
                    action: "模型更新",
                    user: "admin",
                    detail: "切换至 ScholarGuard-Detect-v1",
                  },
                ].map((log, i) => (
                  <tr key={i}>
                    <td className="py-2.5 text-gray-500 whitespace-nowrap">
                      {log.time}
                    </td>
                    <td className="py-2.5">
                      <span className="inline-block px-2 py-0.5 text-xs rounded-full bg-gray-100 text-gray-700">
                        {log.action}
                      </span>
                    </td>
                    <td className="py-2.5 text-gray-600">{log.user}</td>
                    <td className="py-2.5 text-gray-600">{log.detail}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
