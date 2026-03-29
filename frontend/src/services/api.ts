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

export interface DetectResultData {
  task_id: string;
  status: "pending" | "processing" | "completed" | "failed";
  risk_level?: string;
  risk_score?: number;
  llm_confidence?: number;
  statistical_score?: number;
  evidence_completeness?: number;
  paragraph_scores?: ParagraphScore[];
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
 */
export async function getDetectionResult(
  taskId: string
): Promise<DetectResultData> {
  const { data } = await client.get<APIResponse<DetectResultData>>(
    `/detect/${taskId}`
  );
  return data.data;
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
  strategies: string[]
): Promise<SuggestResult> {
  const { data } = await client.post<APIResponse<SuggestResult>>("/suggest", {
    text,
    strategies,
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

/* ---------- Admin API ---------- */

export async function getFormulaParams(): Promise<FormulaParam[]> {
  const { data } = await client.get<APIResponse<FormulaParam[]>>(
    "/admin/formula-params"
  );
  return data.data;
}

export async function updateFormulaParams(
  params: FormulaParam[]
): Promise<{ success: boolean }> {
  const { data } = await client.post<APIResponse<{ success: boolean }>>(
    "/admin/formula-params",
    { params }
  );
  return data.data;
}

export async function getAuditLogs(
  page = 1,
  pageSize = 20
): Promise<{ items: AuditLogEntry[]; total: number }> {
  const { data } = await client.get<
    APIResponse<{ items: AuditLogEntry[]; total: number }>
  >("/admin/audit-logs", {
    params: { page, page_size: pageSize },
  });
  return data.data;
}

export default client;
