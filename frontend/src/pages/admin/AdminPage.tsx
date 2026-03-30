import { useState, useEffect, useCallback } from "react";
import {
  getFormulaParams,
  updateFormulaParams,
  getAuditLogs,
  getUsers,
  updateUserRole,
  updateUserStatus,
  getModelConfig,
  updateModelConfig,
  testModelConnection,
  getUsageStats,
} from "../../services/api";
import type {
  FormulaParam,
  AuditLogEntry,
  UserInfo,
  FullModelConfig,
  ModelRouteEntry,
  UsageStats,
} from "../../services/api";

type Tab = "model" | "formula" | "usage" | "audit" | "users";

/* ================================================================
   Model Selector helpers & sub-components
   ================================================================ */

type Provider = "vllm" | "ollama" | "openai" | "anthropic" | "google";

interface PresetModel {
  id: string;       // LiteLLM model identifier
  label: string;    // 人类可读名称
}

const PROVIDER_META: Record<Provider, { label: string; presets: PresetModel[]; customPlaceholder: string }> = {
  vllm: {
    label: "vLLM (本地)",
    presets: [
      { id: "openai//home/dell/models/Qwen3.5-27B", label: "Qwen3.5-27B" },
      { id: "openai//home/dell/models/Qwen2.5-72B", label: "Qwen2.5-72B" },
    ],
    customPlaceholder: "openai//path/to/model",
  },
  ollama: {
    label: "Ollama (本地)",
    presets: [
      { id: "ollama/qwen2.5:7b", label: "Qwen2.5 7B" },
      { id: "ollama/qwen2.5:14b", label: "Qwen2.5 14B" },
      { id: "ollama/qwen2.5:32b", label: "Qwen2.5 32B" },
      { id: "ollama/llama3:8b", label: "Llama 3 8B" },
      { id: "ollama/deepseek-r1:7b", label: "DeepSeek-R1 7B" },
    ],
    customPlaceholder: "ollama/model-name",
  },
  openai: {
    label: "OpenAI",
    presets: [
      { id: "gpt-4o", label: "GPT-4o" },
      { id: "gpt-4o-mini", label: "GPT-4o Mini" },
      { id: "gpt-4.1", label: "GPT-4.1" },
      { id: "gpt-4.1-mini", label: "GPT-4.1 Mini" },
      { id: "o3-mini", label: "o3-mini" },
    ],
    customPlaceholder: "gpt-4o",
  },
  anthropic: {
    label: "Anthropic",
    presets: [
      { id: "claude-sonnet-4-20250514", label: "Claude Sonnet 4" },
      { id: "claude-opus-4-20250514", label: "Claude Opus 4" },
      { id: "claude-3-5-haiku-20241022", label: "Claude 3.5 Haiku" },
    ],
    customPlaceholder: "claude-sonnet-4-20250514",
  },
  google: {
    label: "Google AI",
    presets: [
      { id: "gemini/gemini-2.5-pro", label: "Gemini 2.5 Pro" },
      { id: "gemini/gemini-2.5-flash", label: "Gemini 2.5 Flash" },
      { id: "gemini/gemini-2.0-flash", label: "Gemini 2.0 Flash" },
    ],
    customPlaceholder: "gemini/gemini-2.5-pro",
  },
};

/** Detect which provider a model identifier belongs to */
function detectProvider(modelId: string): Provider {
  if (modelId.startsWith("openai/")) return "vllm";
  if (modelId.startsWith("ollama/")) return "ollama";
  if (modelId.startsWith("gemini/")) return "google";
  if (modelId.startsWith("claude-")) return "anthropic";
  if (modelId.startsWith("gpt-") || modelId.startsWith("o1") || modelId.startsWith("o3")) return "openai";
  return "vllm";
}

/** Pretty-print model id for display */
function formatModelName(model: string): string {
  const provider = detectProvider(model);
  const meta = PROVIDER_META[provider];
  const preset = meta.presets.find((p) => p.id === model);
  if (preset) return `${preset.label} (${meta.label})`;
  if (model.startsWith("openai/")) {
    const name = model.replace("openai/", "").split("/").pop() || model;
    return `${name} (vLLM)`;
  }
  return model;
}

/** Model selector: provider dropdown → model dropdown → custom input + test */
function ModelSelector({
  value,
  onChange,
  testKey,
  testStatus,
  onTest,
}: {
  value: string;
  onChange: (v: string) => void;
  testKey: string;
  testStatus?: { loading: boolean; success?: boolean; msg?: string };
  onTest: (model: string) => void;
}) {
  const currentProvider = value ? detectProvider(value) : "vllm";
  const meta = PROVIDER_META[currentProvider];
  const isPreset = meta.presets.some((p) => p.id === value);
  const [showCustom, setShowCustom] = useState(!isPreset && !!value);

  const handleProviderChange = (p: Provider) => {
    const newMeta = PROVIDER_META[p];
    setShowCustom(false);
    // Auto-select first preset of the new provider
    if (newMeta.presets.length > 0) {
      onChange(newMeta.presets[0].id);
    } else {
      onChange("");
    }
  };

  const handleModelSelect = (id: string) => {
    if (id === "__custom__") {
      setShowCustom(true);
      onChange("");
    } else {
      setShowCustom(false);
      onChange(id);
    }
  };

  return (
    <div className="space-y-1.5">
      <div className="flex gap-1.5">
        {/* Provider */}
        <select
          className="select text-xs w-[110px] shrink-0"
          value={currentProvider}
          onChange={(e) => handleProviderChange(e.target.value as Provider)}
        >
          {Object.entries(PROVIDER_META).map(([k, v]) => (
            <option key={k} value={k}>
              {v.label}
            </option>
          ))}
        </select>

        {/* Model preset */}
        <select
          className="select text-xs flex-1 min-w-0"
          value={showCustom ? "__custom__" : value}
          onChange={(e) => handleModelSelect(e.target.value)}
        >
          {meta.presets.map((p) => (
            <option key={p.id} value={p.id}>
              {p.label}
            </option>
          ))}
          <option value="__custom__">自定义...</option>
        </select>

        {/* Test */}
        <button
          className={`shrink-0 px-2.5 py-1.5 text-xs rounded-lg border transition-colors whitespace-nowrap ${
            !value
              ? "border-gray-200 text-gray-300 cursor-not-allowed"
              : testStatus?.loading
              ? "border-blue-300 text-blue-500 bg-blue-50 cursor-wait"
              : testStatus?.success === true
              ? "border-green-300 text-green-600 bg-green-50 hover:bg-green-100"
              : testStatus?.success === false
              ? "border-red-300 text-red-600 bg-red-50 hover:bg-red-100"
              : "border-gray-300 text-gray-600 hover:bg-gray-50"
          }`}
          disabled={!value || testStatus?.loading}
          onClick={() => value && onTest(value)}
        >
          {testStatus?.loading ? "测试中..." : "测试"}
        </button>
      </div>

      {/* Custom input */}
      {showCustom && (
        <input
          className="input font-mono text-xs"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={meta.customPlaceholder}
        />
      )}

      {/* Test result */}
      {testStatus && !testStatus.loading && testStatus.success !== undefined && (
        <p
          className={`text-[11px] ${
            testStatus.success ? "text-green-600" : "text-red-600"
          }`}
        >
          {testStatus.success ? "✓ " : "✗ "}
          {testStatus.msg}
        </p>
      )}
    </div>
  );
}

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

  /* ---- Model config state ---- */
  const [modelCfg, setModelCfg] = useState<FullModelConfig | null>(null);
  const [modelLoading, setModelLoading] = useState(false);
  const [modelError, setModelError] = useState("");
  const [modelSaving, setModelSaving] = useState(false);
  const [modelSaved, setModelSaved] = useState(false);
  // Per-model test status: key = "taskType.tier" or "provider"
  const [testStatus, setTestStatus] = useState<
    Record<string, { loading: boolean; success?: boolean; msg?: string }>
  >({});

  /* ---- Usage stats state ---- */
  const [usageStats, setUsageStats] = useState<UsageStats | null>(null);
  const [usageLoading, setUsageLoading] = useState(false);
  const [usageError, setUsageError] = useState("");

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

  /* ---- Load model config ---- */
  const loadModelConfig = useCallback(async () => {
    setModelLoading(true);
    setModelError("");
    try {
      const data = await getModelConfig();
      setModelCfg(data);
      setModelSaved(false);
    } catch (err) {
      setModelError(
        err instanceof Error ? err.message : "加载模型配置失败"
      );
    } finally {
      setModelLoading(false);
    }
  }, []);

  /* ---- Save model config ---- */
  const saveModelConfig = async () => {
    if (!modelCfg) return;
    setModelSaving(true);
    setModelError("");
    try {
      await updateModelConfig(modelCfg);
      setModelSaved(true);
    } catch (err) {
      setModelError(
        err instanceof Error ? err.message : "保存模型配置失败"
      );
    } finally {
      setModelSaving(false);
    }
  };

  /* ---- Test a model ---- */
  const handleTestModel = async (testKey: string, model: string, serviceUrl?: string, apiKey?: string) => {
    if (!model.trim()) return;
    setTestStatus((prev) => ({ ...prev, [testKey]: { loading: true } }));
    try {
      const result = await testModelConnection(model, apiKey, serviceUrl);
      setTestStatus((prev) => ({
        ...prev,
        [testKey]: {
          loading: false,
          success: result.success,
          msg: result.success
            ? `连接成功 (${result.latency_ms}ms)`
            : result.error || "连接失败",
        },
      }));
    } catch (err) {
      setTestStatus((prev) => ({
        ...prev,
        [testKey]: {
          loading: false,
          success: false,
          msg: err instanceof Error ? err.message : "测试请求失败",
        },
      }));
    }
  };

  /* ---- Model config helpers ---- */
  const updateRoute = (task: string, field: keyof ModelRouteEntry, value: string) => {
    if (!modelCfg) return;
    setModelSaved(false);
    setModelCfg({
      ...modelCfg,
      routes: {
        ...modelCfg.routes,
        [task]: { ...modelCfg.routes[task], [field]: value || null },
      },
    });
  };

  const updateServiceUrl = (key: string, value: string) => {
    if (!modelCfg) return;
    setModelSaved(false);
    setModelCfg({
      ...modelCfg,
      service_urls: { ...modelCfg.service_urls, [key]: value },
    });
  };

  const updateApiKey = (provider: string, value: string) => {
    if (!modelCfg) return;
    setModelSaved(false);
    setModelCfg({
      ...modelCfg,
      api_keys: { ...modelCfg.api_keys, [provider]: value },
    });
  };

  /* ---- Load usage stats ---- */
  const loadUsageStats = useCallback(async () => {
    setUsageLoading(true);
    setUsageError("");
    try {
      const data = await getUsageStats();
      setUsageStats(data);
    } catch (err) {
      setUsageError(
        err instanceof Error ? err.message : "加载使用量统计失败"
      );
    } finally {
      setUsageLoading(false);
    }
  }, []);

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
    if (activeTab === "model") {
      loadModelConfig();
    } else if (activeTab === "formula") {
      loadFormula();
    } else if (activeTab === "usage") {
      loadUsageStats();
    } else if (activeTab === "audit") {
      loadAuditLogs(auditPage);
    } else if (activeTab === "users") {
      loadUsers();
    }
  }, [activeTab, auditPage, loadModelConfig, loadFormula, loadUsageStats, loadAuditLogs, loadUsers]);

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
        <div className="space-y-6">
          {/* Info Banner */}
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 text-sm text-blue-800">
            <p className="font-medium mb-1">LLM-Center 架构</p>
            <p>
              每个功能可独立配置主模型、备用模型和降级模型。模型格式示例：
              <code className="bg-blue-100 px-1 rounded">openai/模型路径</code>（vLLM）、
              <code className="bg-blue-100 px-1 rounded">ollama/模型名</code>（Ollama）、
              <code className="bg-blue-100 px-1 rounded">gpt-4o</code>（OpenAI）、
              <code className="bg-blue-100 px-1 rounded">claude-sonnet-4-20250514</code>（Anthropic）、
              <code className="bg-blue-100 px-1 rounded">gemini/gemini-2.5-pro</code>（Google）
            </p>
          </div>

          {modelLoading && (
            <p className="text-sm text-gray-500">加载模型配置中...</p>
          )}

          {modelError && (
            <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm">
              {modelError}
            </div>
          )}

          {modelCfg && (
            <>
              {/* Service URLs */}
              <div className="card space-y-4">
                <h4 className="font-semibold text-gray-900">推理服务地址</h4>
                <div className="grid grid-cols-2 gap-4">
                  {[
                    {
                      key: "vllm_url",
                      label: "vLLM 服务地址",
                      placeholder: "http://192.168.31.18:8001/v1",
                      testKey: "svc_vllm",
                      getTestModel: () =>
                        Object.values(modelCfg.routes).find(
                          (r) => r.primary?.startsWith("openai/")
                        )?.primary || "",
                    },
                    {
                      key: "ollama_url",
                      label: "Ollama 服务地址",
                      placeholder: "http://localhost:11434",
                      testKey: "svc_ollama",
                      getTestModel: () => "ollama/qwen2.5:0.5b",
                    },
                  ].map(({ key, label, placeholder, testKey: tk, getTestModel }) => {
                    const ts = testStatus[tk];
                    return (
                      <div key={key}>
                        <label className="block text-xs font-medium text-gray-500 mb-1">
                          {label}
                        </label>
                        <div className="flex gap-2">
                          <input
                            className="input flex-1 font-mono text-xs"
                            value={modelCfg.service_urls[key] || ""}
                            onChange={(e) =>
                              updateServiceUrl(key, e.target.value)
                            }
                            placeholder={placeholder}
                          />
                          <button
                            className={`shrink-0 px-2.5 py-1.5 text-xs rounded-lg border transition-colors whitespace-nowrap ${
                              ts?.loading
                                ? "border-blue-300 text-blue-500 bg-blue-50 cursor-wait"
                                : ts?.success === true
                                ? "border-green-300 text-green-600 bg-green-50"
                                : ts?.success === false
                                ? "border-red-300 text-red-600 bg-red-50"
                                : "border-gray-300 text-gray-600 hover:bg-gray-50"
                            }`}
                            disabled={ts?.loading}
                            onClick={() => {
                              const m = getTestModel();
                              if (m) handleTestModel(tk, m, modelCfg.service_urls[key]);
                            }}
                          >
                            {ts?.loading ? "测试中..." : "测试"}
                          </button>
                        </div>
                        {ts && !ts.loading && ts.success !== undefined && (
                          <p className={`text-[11px] mt-1 ${ts.success ? "text-green-600" : "text-red-600"}`}>
                            {ts.success ? "✓ " : "✗ "}{ts.msg}
                          </p>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* API Keys */}
              <div className="card space-y-4">
                <h4 className="font-semibold text-gray-900">
                  远程模型 API Key
                </h4>
                <p className="text-xs text-gray-500">
                  配置后可在路由中使用对应厂商的模型作为备用或主模型。留空表示不启用。
                </p>
                <div className="grid grid-cols-3 gap-4">
                  {[
                    {
                      provider: "openai",
                      label: "OpenAI",
                      placeholder: "sk-...",
                      testModel: "gpt-4o",
                    },
                    {
                      provider: "anthropic",
                      label: "Anthropic",
                      placeholder: "sk-ant-...",
                      testModel: "claude-sonnet-4-20250514",
                    },
                    {
                      provider: "google",
                      label: "Google AI",
                      placeholder: "AIza...",
                      testModel: "gemini/gemini-2.5-pro",
                    },
                  ].map(({ provider, label, placeholder, testModel }) => {
                    const ts = testStatus[`key_${provider}`];
                    return (
                    <div key={provider}>
                      <label className="block text-xs font-medium text-gray-500 mb-1">
                        {label} API Key
                        {modelCfg.api_keys_set?.[provider] && (
                          <span className="ml-1.5 text-green-600">
                            (已配置)
                          </span>
                        )}
                      </label>
                      <div className="flex gap-2">
                        <input
                          type="password"
                          className="input flex-1 font-mono text-xs"
                          value={modelCfg.api_keys[provider] || ""}
                          onChange={(e) =>
                            updateApiKey(provider, e.target.value)
                          }
                          placeholder={placeholder}
                        />
                        <button
                          className={`shrink-0 px-2.5 py-1.5 text-xs rounded-lg border transition-colors whitespace-nowrap ${
                            ts?.loading
                              ? "border-blue-300 text-blue-500 bg-blue-50 cursor-wait"
                              : ts?.success === true
                              ? "border-green-300 text-green-600 bg-green-50"
                              : ts?.success === false
                              ? "border-red-300 text-red-600 bg-red-50"
                              : "border-gray-300 text-gray-600 hover:bg-gray-50"
                          }`}
                          disabled={ts?.loading}
                          onClick={() =>
                            handleTestModel(
                              `key_${provider}`,
                              testModel,
                              undefined,
                              modelCfg.api_keys[provider] || undefined
                            )
                          }
                        >
                          {ts?.loading ? "测试中..." : "测试"}
                        </button>
                      </div>
                      {ts && !ts.loading && ts.success !== undefined && (
                        <p className={`text-[11px] mt-1 ${ts.success ? "text-green-600" : "text-red-600"}`}>
                          {ts.success ? "✓ " : "✗ "}{ts.msg}
                        </p>
                      )}
                    </div>
                  );
                  })}
                </div>
              </div>

              {/* Per-Task Model Routing */}
              <div className="card space-y-5">
                <div>
                  <h4 className="font-semibold text-gray-900">
                    功能模型路由
                  </h4>
                  <p className="text-xs text-gray-500 mt-1">
                    为每个功能配置三级模型降级链。选择厂商和模型后点「测试」验证连通性，通过后点底部「保存配置」。
                  </p>
                </div>

                {Object.entries(modelCfg.routes).map(([taskType, route]) => {
                  const taskMeta: Record<
                    string,
                    { label: string; icon: string }
                  > = {
                    detection: { label: "AI 检测", icon: "🔍" },
                    suggestion: { label: "写作建议", icon: "✍️" },
                    translation: { label: "翻译润色", icon: "🌐" },
                  };
                  const tm = taskMeta[taskType] || {
                    label: taskType,
                    icon: "📦",
                  };

                  const resolveServiceUrl = (model: string) => {
                    if (model.startsWith("openai/"))
                      return modelCfg.service_urls.vllm_url;
                    if (model.startsWith("ollama/"))
                      return modelCfg.service_urls.ollama_url;
                    return undefined;
                  };

                  const resolveApiKey = (model: string) => {
                    if (model.startsWith("gpt-") || model.startsWith("o1") || model.startsWith("o3") || model.startsWith("o4"))
                      return modelCfg.api_keys.openai || undefined;
                    if (model.startsWith("claude-"))
                      return modelCfg.api_keys.anthropic || undefined;
                    if (model.startsWith("gemini/"))
                      return modelCfg.api_keys.google || undefined;
                    return undefined;
                  };

                  return (
                    <div
                      key={taskType}
                      className="border border-gray-200 rounded-lg p-4 space-y-3"
                    >
                      <div className="flex items-center gap-2">
                        <span className="text-lg">{tm.icon}</span>
                        <span className="font-medium text-gray-900">
                          {tm.label}
                        </span>
                        {route.source === "database" && (
                          <span className="px-2 py-0.5 text-[10px] rounded-full bg-purple-100 text-purple-700">
                            自定义
                          </span>
                        )}
                      </div>
                      <div className="grid grid-cols-3 gap-4">
                        {/* Primary */}
                        <div>
                          <label className="block text-xs font-medium text-gray-500 mb-1.5">
                            <span className="inline-block w-2 h-2 rounded-full bg-green-500 mr-1" />
                            主模型
                          </label>
                          <ModelSelector
                            value={route.primary || ""}
                            onChange={(v) => updateRoute(taskType, "primary", v)}
                            testKey={`${taskType}.primary`}
                            testStatus={testStatus[`${taskType}.primary`]}
                            onTest={(m) =>
                              handleTestModel(
                                `${taskType}.primary`,
                                m,
                                resolveServiceUrl(m),
                                resolveApiKey(m)
                              )
                            }
                          />
                        </div>
                        {/* Fallback */}
                        <div>
                          <label className="block text-xs font-medium text-gray-500 mb-1.5">
                            <span className="inline-block w-2 h-2 rounded-full bg-yellow-400 mr-1" />
                            备用模型
                          </label>
                          <ModelSelector
                            value={route.fallback || ""}
                            onChange={(v) => updateRoute(taskType, "fallback", v)}
                            testKey={`${taskType}.fallback`}
                            testStatus={testStatus[`${taskType}.fallback`]}
                            onTest={(m) =>
                              handleTestModel(
                                `${taskType}.fallback`,
                                m,
                                resolveServiceUrl(m),
                                resolveApiKey(m)
                              )
                            }
                          />
                        </div>
                        {/* Degradation */}
                        <div>
                          <label className="block text-xs font-medium text-gray-500 mb-1.5">
                            <span className="inline-block w-2 h-2 rounded-full bg-gray-300 mr-1" />
                            降级模型
                          </label>
                          <ModelSelector
                            value={route.degradation || ""}
                            onChange={(v) =>
                              updateRoute(taskType, "degradation", v)
                            }
                            testKey={`${taskType}.degradation`}
                            testStatus={testStatus[`${taskType}.degradation`]}
                            onTest={(m) =>
                              handleTestModel(
                                `${taskType}.degradation`,
                                m,
                                resolveServiceUrl(m),
                                resolveApiKey(m)
                              )
                            }
                          />
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* Save */}
              <div className="flex items-center gap-3">
                <button
                  className="btn-primary"
                  disabled={modelSaving}
                  onClick={saveModelConfig}
                >
                  {modelSaving ? "保存中..." : "保存配置"}
                </button>
                {modelSaved && (
                  <span className="text-xs text-green-600 font-medium">
                    配置已保存
                  </span>
                )}
                <span className="text-xs text-gray-400">
                  注意：API Key 和服务地址修改仅在本次运行时生效，重启后需重新配置或修改
                  .env 文件
                </span>
              </div>
            </>
          )}
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
          {usageLoading && (
            <p className="text-sm text-gray-500">加载使用量统计中...</p>
          )}

          {usageError && (
            <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm">
              {usageError}
            </div>
          )}

          {usageStats && (
            <>
              <div className="grid grid-cols-4 gap-4">
                <div className="card text-center">
                  <p className="text-2xl font-bold text-gray-900">
                    {usageStats.detections_today}
                  </p>
                  <p className="text-xs text-gray-500 mt-1">今日检测量</p>
                </div>
                <div className="card text-center">
                  <p className="text-2xl font-bold text-gray-900">
                    {usageStats.total_detections.toLocaleString()}
                  </p>
                  <p className="text-xs text-gray-500 mt-1">累计检测量</p>
                </div>
                <div className="card text-center">
                  <p className="text-2xl font-bold text-gray-900">
                    {usageStats.average_processing_ms > 0
                      ? `${(usageStats.average_processing_ms / 1000).toFixed(1)}s`
                      : "--"}
                  </p>
                  <p className="text-xs text-gray-500 mt-1">平均响应时间</p>
                </div>
                <div className="card text-center">
                  <p className="text-2xl font-bold text-gray-900">
                    {usageStats.total_reviews}
                  </p>
                  <p className="text-xs text-gray-500 mt-1">累计复核数</p>
                </div>
              </div>

              <div className="grid grid-cols-3 gap-4">
                <div className="card text-center">
                  <p className="text-lg font-bold text-gray-900">
                    {usageStats.total_suggestions}
                  </p>
                  <p className="text-xs text-gray-500 mt-1">写作建议次数</p>
                </div>
                <div className="card text-center">
                  <p className="text-lg font-bold text-gray-900">
                    {usageStats.total_appeals}
                  </p>
                  <p className="text-xs text-gray-500 mt-1">申诉次数</p>
                </div>
                <div className="card text-center">
                  <p className="text-lg font-bold text-gray-900">
                    {usageStats.active_users_24h}
                  </p>
                  <p className="text-xs text-gray-500 mt-1">24h 活跃用户</p>
                </div>
              </div>
            </>
          )}

          {!usageLoading && !usageStats && !usageError && (
            <div className="card text-center py-8">
              <p className="text-sm text-gray-400">暂无使用量数据</p>
            </div>
          )}
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
