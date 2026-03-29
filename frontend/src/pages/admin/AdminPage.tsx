import { useState, useEffect, useCallback } from "react";
import {
  getFormulaParams,
  updateFormulaParams,
  getAuditLogs,
  getUsers,
  updateUserRole,
  updateUserStatus,
} from "../../services/api";
import type { FormulaParam, AuditLogEntry, UserInfo } from "../../services/api";

type Tab = "model" | "formula" | "usage" | "audit" | "users";

export default function AdminPage() {
  const [activeTab, setActiveTab] = useState<Tab>("model");

  /* ---- Formula state ---- */
  const [formulaParams, setFormulaParams] = useState<FormulaParam[]>([]);
  const [formulaLoading, setFormulaLoading] = useState(false);
  const [formulaError, setFormulaError] = useState("");
  const [formulaSaving, setFormulaSaving] = useState(false);
  const [formulaSaved, setFormulaSaved] = useState(false);

  /* ---- Audit state ---- */
  const [auditLogs, setAuditLogs] = useState<AuditLogEntry[]>([]);
  const [auditLoading, setAuditLoading] = useState(false);
  const [auditError, setAuditError] = useState("");
  const [auditTotal, setAuditTotal] = useState(0);
  const [auditPage, setAuditPage] = useState(1);

  /* ---- Users state ---- */
  const [users, setUsers] = useState<UserInfo[]>([]);
  const [usersLoading, setUsersLoading] = useState(false);
  const [usersError, setUsersError] = useState("");

  const tabs: { key: Tab; label: string }[] = [
    { key: "model", label: "模型配置" },
    { key: "formula", label: "公式参数" },
    { key: "usage", label: "使用量统计" },
    { key: "audit", label: "审计日志" },
    { key: "users", label: "用户管理" },
  ];

  /* ---- Load formula params ---- */
  const loadFormula = useCallback(async () => {
    setFormulaLoading(true);
    setFormulaError("");
    try {
      const params = await getFormulaParams();
      setFormulaParams(params);
    } catch (err) {
      setFormulaError(
        err instanceof Error ? err.message : "加载公式参数失败"
      );
    } finally {
      setFormulaLoading(false);
    }
  }, []);

  /* ---- Save formula params ---- */
  const saveFormula = async () => {
    setFormulaSaving(true);
    setFormulaSaved(false);
    try {
      await updateFormulaParams(formulaParams);
      setFormulaSaved(true);
    } catch (err) {
      setFormulaError(
        err instanceof Error ? err.message : "保存公式参数失败"
      );
    } finally {
      setFormulaSaving(false);
    }
  };

  /* ---- Load audit logs ---- */
  const loadAuditLogs = useCallback(async (page: number) => {
    setAuditLoading(true);
    setAuditError("");
    try {
      const result = await getAuditLogs(page, 20);
      setAuditLogs(result.items);
      setAuditTotal(result.total);
    } catch (err) {
      setAuditError(
        err instanceof Error ? err.message : "加载审计日志失败"
      );
    } finally {
      setAuditLoading(false);
    }
  }, []);

  /* ---- Load users ---- */
  const loadUsers = useCallback(async () => {
    setUsersLoading(true);
    setUsersError("");
    try {
      const data = await getUsers();
      setUsers(data);
    } catch (err) {
      setUsersError(
        err instanceof Error ? err.message : "加载用户列表失败"
      );
    } finally {
      setUsersLoading(false);
    }
  }, []);

  /* ---- Handle role change ---- */
  const handleRoleChange = async (userId: string, newRole: string) => {
    try {
      const updated = await updateUserRole(userId, newRole);
      setUsers((prev) =>
        prev.map((u) => (u.id === updated.id ? updated : u))
      );
    } catch (err) {
      setUsersError(
        err instanceof Error ? err.message : "更新角色失败"
      );
    }
  };

  /* ---- Handle status toggle ---- */
  const handleStatusToggle = async (userId: string) => {
    try {
      const updated = await updateUserStatus(userId);
      setUsers((prev) =>
        prev.map((u) => (u.id === updated.id ? updated : u))
      );
    } catch (err) {
      setUsersError(
        err instanceof Error ? err.message : "更新状态失败"
      );
    }
  };

  /* ---- Load data when switching tabs ---- */
  useEffect(() => {
    if (activeTab === "formula") {
      loadFormula();
    } else if (activeTab === "audit") {
      loadAuditLogs(auditPage);
    } else if (activeTab === "users") {
      loadUsers();
    }
  }, [activeTab, auditPage, loadFormula, loadAuditLogs, loadUsers]);

  const handleParamChange = (index: number, value: number) => {
    setFormulaParams((prev) =>
      prev.map((p, i) => (i === index ? { ...p, value } : p))
    );
    setFormulaSaved(false);
  };

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

          {formulaLoading && (
            <p className="text-sm text-gray-500">加载中...</p>
          )}

          {formulaError && (
            <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm">
              {formulaError}
            </div>
          )}

          {!formulaLoading && formulaParams.length > 0 && (
            <div className="grid grid-cols-4 gap-4">
              {formulaParams.map((p, i) => (
                <div key={p.key}>
                  <label className="block text-xs font-medium text-gray-500 mb-1">
                    {p.label || p.key}
                  </label>
                  <input
                    type="number"
                    className="input"
                    value={p.value}
                    step={p.step ?? 0.05}
                    min={p.min ?? 0}
                    max={p.max ?? 1}
                    onChange={(e) =>
                      handleParamChange(i, parseFloat(e.target.value) || 0)
                    }
                  />
                </div>
              ))}
            </div>
          )}

          {!formulaLoading && formulaParams.length === 0 && !formulaError && (
            <p className="text-sm text-gray-400">暂无公式参数数据</p>
          )}

          <div className="flex items-center gap-3">
            <button
              className="btn-primary"
              disabled={formulaSaving || formulaParams.length === 0}
              onClick={saveFormula}
            >
              {formulaSaving ? "保存中..." : "保存参数"}
            </button>
            {formulaSaved && (
              <span className="text-xs text-green-600 font-medium">
                保存成功
              </span>
            )}
          </div>
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
                      s.trend.startsWith("+")
                        ? "text-green-600"
                        : "text-blue-600"
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

          {auditLoading && (
            <p className="text-sm text-gray-500 mb-4">加载中...</p>
          )}

          {auditError && (
            <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm mb-4">
              {auditError}
            </div>
          )}

          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200 text-left">
                  <th className="pb-2 text-xs font-medium text-gray-500">
                    时间
                  </th>
                  <th className="pb-2 text-xs font-medium text-gray-500">
                    操作
                  </th>
                  <th className="pb-2 text-xs font-medium text-gray-500">
                    用户
                  </th>
                  <th className="pb-2 text-xs font-medium text-gray-500">
                    详情
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {auditLogs.map((log) => (
                  <tr key={log.id}>
                    <td className="py-2.5 text-gray-500 whitespace-nowrap">
                      {log.timestamp}
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
                {!auditLoading && auditLogs.length === 0 && (
                  <tr>
                    <td
                      colSpan={4}
                      className="py-8 text-center text-gray-400 text-sm"
                    >
                      暂无审计日志
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          {auditTotal > 20 && (
            <div className="flex items-center justify-between mt-4 pt-4 border-t border-gray-100">
              <p className="text-xs text-gray-500">
                共 {auditTotal} 条记录
              </p>
              <div className="flex gap-2">
                <button
                  className="btn-secondary text-xs"
                  disabled={auditPage <= 1}
                  onClick={() => setAuditPage((p) => Math.max(1, p - 1))}
                >
                  上一页
                </button>
                <button
                  className="btn-secondary text-xs"
                  disabled={auditPage * 20 >= auditTotal}
                  onClick={() => setAuditPage((p) => p + 1)}
                >
                  下一页
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* User Management */}
      {activeTab === "users" && (
        <div className="card">
          <h4 className="font-semibold text-gray-900 mb-4">用户管理</h4>

          {usersLoading && (
            <p className="text-sm text-gray-500 mb-4">加载中...</p>
          )}

          {usersError && (
            <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm mb-4">
              {usersError}
            </div>
          )}

          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200 text-left">
                  <th className="pb-2 text-xs font-medium text-gray-500">
                    用户名
                  </th>
                  <th className="pb-2 text-xs font-medium text-gray-500">
                    邮箱
                  </th>
                  <th className="pb-2 text-xs font-medium text-gray-500">
                    角色
                  </th>
                  <th className="pb-2 text-xs font-medium text-gray-500">
                    状态
                  </th>
                  <th className="pb-2 text-xs font-medium text-gray-500">
                    注册时间
                  </th>
                  <th className="pb-2 text-xs font-medium text-gray-500">
                    操作
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {users.map((u) => (
                  <tr key={u.id}>
                    <td className="py-2.5 text-gray-900 font-medium">
                      {u.username}
                    </td>
                    <td className="py-2.5 text-gray-600">{u.email}</td>
                    <td className="py-2.5">
                      <span
                        className={`inline-block px-2 py-0.5 text-xs rounded-full ${
                          u.role === "admin"
                            ? "bg-purple-100 text-purple-700"
                            : u.role === "reviewer"
                            ? "bg-blue-100 text-blue-700"
                            : "bg-gray-100 text-gray-700"
                        }`}
                      >
                        {u.role}
                      </span>
                    </td>
                    <td className="py-2.5">
                      <span
                        className={`inline-block px-2 py-0.5 text-xs rounded-full ${
                          u.is_active
                            ? "bg-green-100 text-green-700"
                            : "bg-red-100 text-red-700"
                        }`}
                      >
                        {u.is_active ? "活跃" : "已禁用"}
                      </span>
                    </td>
                    <td className="py-2.5 text-gray-500 whitespace-nowrap">
                      {new Date(u.created_at).toLocaleDateString("zh-CN")}
                    </td>
                    <td className="py-2.5">
                      <div className="flex items-center gap-2">
                        <select
                          className="text-xs border border-gray-200 rounded px-2 py-1 bg-white"
                          value={u.role}
                          onChange={(e) =>
                            handleRoleChange(u.id, e.target.value)
                          }
                        >
                          <option value="detector">detector</option>
                          <option value="reviewer">reviewer</option>
                          <option value="admin">admin</option>
                        </select>
                        <button
                          className={`text-xs px-2 py-1 rounded ${
                            u.is_active
                              ? "bg-red-50 text-red-600 hover:bg-red-100"
                              : "bg-green-50 text-green-600 hover:bg-green-100"
                          }`}
                          onClick={() => handleStatusToggle(u.id)}
                        >
                          {u.is_active ? "禁用" : "启用"}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
                {!usersLoading && users.length === 0 && !usersError && (
                  <tr>
                    <td
                      colSpan={6}
                      className="py-8 text-center text-gray-400 text-sm"
                    >
                      暂无用户数据
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
