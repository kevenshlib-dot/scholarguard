import axios from "axios";

const BASE_URL = import.meta.env.VITE_API_BASE_URL || "/api/v1";
const TOKEN_KEY = "sg_token";

const client = axios.create({
  baseURL: BASE_URL,
  timeout: 60_000,
  headers: {
    "Content-Type": "application/json",
    "X-API-Key": "sg-test-key-001",
  },
});

// On init: restore Authorization header from localStorage
const storedToken = localStorage.getItem(TOKEN_KEY);
if (storedToken) {
  client.defaults.headers.common["Authorization"] = `Bearer ${storedToken}`;
}

// Request interceptor: attach Bearer token to every request
client.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY);
  if (token && config.headers) {
    config.headers["Authorization"] = `Bearer ${token}`;
  }
  return config;
});

// Response interceptor: on 401, clear auth and redirect to /login
client.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem(TOKEN_KEY);
      localStorage.removeItem("sg_user");
      delete client.defaults.headers.common["Authorization"];
      // Only redirect if not already on login/register page
      if (
        !window.location.pathname.startsWith("/login") &&
        !window.location.pathname.startsWith("/register")
      ) {
        window.location.href = "/login";
      }
    }
    return Promise.reject(error);
  }
);

/* ---------- API Envelope ---------- */

export interface APIResponse<T> {
  code: number;
  message: string;
  data: T;
  meta?: Record<string, unknown>;
}

/* ---------- Detection Types ---------- */

export interface DetectRequest {
  text: string;
  granularity: "document" | "paragraph" | "sentence";
  language: "auto" | "zh" | "en";
  discipline: string;
}

export interface DetectTaskData {
  task_id: string;
  status: string;
}

export interface ParagraphScore {
  index: number;
  text: string;
  score: number;
  risk_level: string;
}

export interface FlaggedSegment {
  start_char: number;
  end_char: number;
  text_snippet: string;
  issue: string;
}

export interface DetectResultData {
  task_id: string;
  status: "pending" | "processing" | "completed" | "failed";
  risk_level?: string;
  risk_score?: number;
  llm_confidence?: number;
  statistical_score?: number;
  evidence_completeness?: number;
  paragraph_scores?: ParagraphScore[];
  flagged_segments?: FlaggedSegment[];
  evidence_summary?: string;
  recommendations?: string[];
  uncertainty_note?: string;
  error?: string;
}

export interface FeedbackRequest {
  detection_id: string;
  type: "agree" | "disagree" | "partial";
  comment: string;
}

export interface SuggestRequest {
  text: string;
  strategies: string[];
}

export interface Suggestion {
  strategy: string;
  original: string;
  suggested: string;
  explanation: string;
}

export interface SuggestResult {
  suggestions: Suggestion[];
}

export interface SuggestionItem {
  suggestion_id: string;
  type: string;
  original_text: string;
  suggested_text: string;
  explanation: string;
  offset_start: number;
  offset_end: number;
  confidence: number;
}

export interface SuggestResultData {
  suggestions: SuggestionItem[];
  original_risk_score: number | null;
  estimated_risk_score: number | null;
}

export interface LiteratureItem {
  title: string;
  authors: string[];
  year: number;
  abstract: string;
  source: string;
}

export interface ReviewItem {
  id: string;
  detection_id: string;
  submitted_at: string;
  risk_level: string;
  risk_score: number;
  status: "pending" | "reviewing" | "resolved";
  text_preview: string;
}

/* ---------- Admin Types ---------- */

export interface FormulaParam {
  key: string;
  label: string;
  value: number;
  min?: number;
  max?: number;
  step?: number;
}

export interface AuditLogEntry {
  id: string;
  timestamp: string;
  action: string;
  user: string;
  detail: string;
}

/** Raw shape returned by the backend */
interface RawAuditLogEntry {
  log_id: string;
  timestamp: string;
  user_id: string;
  action: string;
  resource: string;
  details: Record<string, unknown> | null;
}

/* ---------- API functions ---------- */

/**
 * Submit text for detection. Returns 202 with task_id.
 */
export async function submitDetection(
  text: string,
  granularity: "document" | "paragraph" | "sentence",
  language: "auto" | "zh" | "en",
  discipline: string
): Promise<DetectTaskData> {
  const { data } = await client.post<APIResponse<DetectTaskData>>("/detect", {
    text,
    granularity,
    language,
    discipline,
  });
  return data.data;
}

/**
 * Get the current status / result for a detection task.
 * The API nests scores inside data.result; we flatten them to the top level.
 */
export async function getDetectionResult(
  taskId: string
): Promise<DetectResultData> {
  const { data } = await client.get<APIResponse<{
    task_id: string;
    status: string;
    result?: {
      detection_id?: string;
      risk_score?: number;
      risk_level?: string;
      llm_confidence?: number;
      statistical_score?: number;
      formula_version?: string;
      param_version?: string;
      language?: string;
      [key: string]: unknown;
    };
  }>>(
    `/detect/${taskId}`
  );
  const raw = data.data;
  const r = raw.result;
  // Flatten: merge nested result fields to top level
  return {
    task_id: raw.task_id,
    status: raw.status as DetectResultData["status"],
    risk_score: r?.risk_score,
    risk_level: r?.risk_level,
    llm_confidence: r?.llm_confidence,
    statistical_score: r?.statistical_score,
    flagged_segments: (r?.flagged_segments as FlaggedSegment[] | undefined) ?? undefined,
    evidence_summary: (r?.evidence_summary as string | undefined) ?? undefined,
    recommendations: (r?.recommendations as string[] | undefined) ?? undefined,
    uncertainty_note: (r?.uncertainty_notes as string | undefined) ?? undefined,
  };
}

/**
 * Poll GET /detect/{taskId} every 5 seconds until status is "completed" or "failed".
 * Resolves with the final result. Rejects after maxAttempts (default 60 = 5 min).
 */
export function pollDetectionResult(
  taskId: string,
  onProgress?: (status: string) => void,
  intervalMs = 5000,
  maxAttempts = 60
): Promise<DetectResultData> {
  return new Promise((resolve, reject) => {
    let attempts = 0;

    const tick = async () => {
      try {
        attempts++;
        const result = await getDetectionResult(taskId);

        if (result.status === "completed" || result.status === "failed") {
          resolve(result);
          return;
        }

        if (attempts >= maxAttempts) {
          resolve({
            ...result,
            status: "failed" as const,
            error: "检测超时，请稍后重试",
          });
          return;
        }

        onProgress?.(result.status);
        setTimeout(tick, intervalMs);
      } catch (err) {
        reject(err);
      }
    };

    tick();
  });
}

export async function submitFeedback(
  detectionId: string,
  type: "agree" | "disagree" | "partial",
  comment: string
): Promise<{ success: boolean }> {
  const { data } = await client.post<APIResponse<{ success: boolean }>>(
    "/feedback",
    {
      detection_id: detectionId,
      type,
      comment,
    }
  );
  return data.data;
}

export async function getSuggestions(
  text: string,
  strategies: string[],
  detectionId?: string,
  language?: string,
  discipline?: string
): Promise<SuggestResultData> {
  const { data } = await client.post<APIResponse<SuggestResultData>>("/suggest", {
    text,
    focus: strategies,
    detection_id: detectionId || undefined,
    language: language || undefined,
    discipline: discipline || undefined,
  });
  return data.data;
}

export async function searchLiterature(
  query: string,
  topK: number = 5
): Promise<{ results: LiteratureItem[] }> {
  const { data } = await client.post<
    APIResponse<{ results: LiteratureItem[] }>
  >("/research/search", { query, top_k: topK });
  return data.data;
}

/* ---------- Review API ---------- */

export async function getReviewList(
  status?: string
): Promise<{ items: ReviewItem[] }> {
  const { data } = await client.get<APIResponse<{ items: ReviewItem[] }>>(
    "/reviews",
    {
      params: { status },
    }
  );
  return data.data;
}

export async function submitReview(
  reviewId: string,
  decision: "maintain" | "adjust" | "dismiss",
  comment: string
): Promise<{ success: boolean }> {
  const { data } = await client.post<APIResponse<{ success: boolean }>>(
    `/reviews/${reviewId}/decide`,
    { decision, comment }
  );
  return data.data;
}

/* ---------- User Management Types ---------- */

export interface UserInfo {
  id: string;
  username: string;
  email: string;
  role: string;
  is_active: boolean;
  created_at: string;
  organization_name: string | null;
}

/* ---------- Model Config Types ---------- */

export interface ModelRouteEntry {
  primary: string;
  fallback: string | null;
  degradation: string | null;
  source?: string;
}

export interface FullModelConfig {
  routes: Record<string, ModelRouteEntry>;
  service_urls: Record<string, string>;
  api_keys: Record<string, string>;
  api_keys_set?: Record<string, boolean>;
}

export interface ModelTestResult {
  success: boolean;
  error?: string;
  latency_ms: number;
  response_preview?: string;
  model?: string;
}

/* ---------- Admin API ---------- */

export async function getModelConfig(): Promise<FullModelConfig> {
  const { data } = await client.get<APIResponse<FullModelConfig>>(
    "/models/config"
  );
  return data.data;
}

export async function updateModelConfig(
  config: FullModelConfig
): Promise<{ success: boolean }> {
  const { data } = await client.put<
    APIResponse<{ success: boolean }>
  >("/models/config", config);
  return data.data;
}

export async function testModelConnection(
  model: string,
  apiKey?: string,
  serviceUrl?: string
): Promise<ModelTestResult> {
  const { data } = await client.post<APIResponse<ModelTestResult>>(
    "/models/test",
    { model, api_key: apiKey || undefined, service_url: serviceUrl || undefined }
  );
  return data.data;
}

export interface UsageStats {
  total_detections: number;
  total_suggestions: number;
  total_reviews: number;
  total_appeals: number;
  detections_today: number;
  average_processing_ms: number;
  active_users_24h: number;
}

export async function getUsageStats(): Promise<UsageStats> {
  const { data } = await client.get<APIResponse<UsageStats>>("/usage");
  return data.data;
}

/** Raw shape from backend formula-params endpoint */
interface RawFormulaParams {
  formula_version: string;
  param_version: string;
  weights: Record<string, number>;
  thresholds: Record<string, number>;
  updated_at?: string;
  updated_by?: string;
}

const WEIGHT_LABELS: Record<string, string> = {
  llm_confidence: "LLM 置信度 (w1)",
  statistical_score: "统计特征 (w2)",
  stylistic_score: "风格特征 (w3)",
};

const THRESHOLD_LABELS: Record<string, string> = {
  low_max: "低风险上限",
  medium_max: "中风险上限",
  high_max: "高风险上限",
};

export async function getFormulaParams(): Promise<FormulaParam[]> {
  const { data } = await client.get<APIResponse<RawFormulaParams>>(
    "/admin/formula-params"
  );
  const raw = data.data;
  const params: FormulaParam[] = [];

  // Convert weights dict to FormulaParam[]
  for (const [key, value] of Object.entries(raw.weights || {})) {
    params.push({
      key: `w_${key}`,
      label: WEIGHT_LABELS[key] || key,
      value,
      min: 0,
      max: 1,
      step: 0.05,
    });
  }
  // Convert thresholds dict to FormulaParam[]
  for (const [key, value] of Object.entries(raw.thresholds || {})) {
    params.push({
      key: `t_${key}`,
      label: THRESHOLD_LABELS[key] || key,
      value,
      min: 0,
      max: 1,
      step: 0.05,
    });
  }
  return params;
}

export async function updateFormulaParams(
  params: FormulaParam[]
): Promise<{ success: boolean }> {
  // Convert FormulaParam[] back to { weights, thresholds } for the backend
  const weights: Record<string, number> = {};
  const thresholds: Record<string, number> = {};
  for (const p of params) {
    if (p.key.startsWith("w_")) {
      weights[p.key.slice(2)] = p.value;
    } else if (p.key.startsWith("t_")) {
      thresholds[p.key.slice(2)] = p.value;
    }
  }
  const { data } = await client.put<APIResponse<RawFormulaParams>>(
    "/admin/formula-params",
    { weights, thresholds }
  );
  return { success: !!data.data };
}

export async function getAuditLogs(
  page = 1,
  pageSize = 20
): Promise<{ items: AuditLogEntry[]; total: number }> {
  const { data } = await client.get<
    APIResponse<RawAuditLogEntry[]> & { meta?: { total?: number } }
  >("/admin/audit-logs", {
    params: { page, page_size: pageSize },
  });

  // Backend returns array in data + total in meta; map field names
  const rawItems: RawAuditLogEntry[] = Array.isArray(data.data)
    ? data.data
    : [];
  const items: AuditLogEntry[] = rawItems.map((r) => ({
    id: r.log_id,
    timestamp: r.timestamp,
    action: r.action,
    user: r.user_id,
    detail: r.resource + (r.details ? ` ${JSON.stringify(r.details)}` : ""),
  }));
  const total = (data.meta as Record<string, unknown>)?.total as number ?? items.length;
  return { items, total };
}

/* ---------- User Management API ---------- */

export async function getUsers(): Promise<UserInfo[]> {
  const { data } = await client.get<APIResponse<UserInfo[]>>("/admin/users");
  return data.data;
}

export async function updateUserRole(
  userId: string,
  role: string
): Promise<UserInfo> {
  const { data } = await client.put<APIResponse<UserInfo>>(
    `/admin/users/${userId}/role`,
    { role }
  );
  return data.data;
}

export async function updateUserStatus(
  userId: string
): Promise<UserInfo> {
  const { data } = await client.put<APIResponse<UserInfo>>(
    `/admin/users/${userId}/status`
  );
  return data.data;
}

export default client;
