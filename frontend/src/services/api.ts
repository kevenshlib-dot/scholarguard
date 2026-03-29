import axios from "axios";

const BASE_URL = import.meta.env.VITE_API_BASE_URL || "/api/v1";

const client = axios.create({
  baseURL: BASE_URL,
  timeout: 60_000,
  headers: { "Content-Type": "application/json" },
});

/* ---------- Types ---------- */

export interface DetectRequest {
  text: string;
  granularity: "document" | "paragraph" | "sentence";
  language: "auto" | "zh" | "en";
  discipline: string;
}

export interface DetectTaskResponse {
  task_id: string;
  status: string;
  message?: string;
}

export interface ParagraphScore {
  index: number;
  text: string;
  score: number;
  risk_level: string;
}

export interface DetectResult {
  task_id: string;
  status: "pending" | "processing" | "completed" | "failed";
  risk_level?: string;
  risk_score?: number;
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

/* ---------- API functions ---------- */

export async function detectText(
  text: string,
  granularity: "document" | "paragraph" | "sentence",
  language: "auto" | "zh" | "en",
  discipline: string
): Promise<DetectTaskResponse> {
  const { data } = await client.post<DetectTaskResponse>("/detect", {
    text,
    granularity,
    language,
    discipline,
  });
  return data;
}

export async function getDetectionResult(
  taskId: string
): Promise<DetectResult> {
  const { data } = await client.get<DetectResult>(`/detect/${taskId}`);
  return data;
}

export async function submitFeedback(
  detectionId: string,
  type: "agree" | "disagree" | "partial",
  comment: string
): Promise<{ success: boolean }> {
  const { data } = await client.post<{ success: boolean }>("/feedback", {
    detection_id: detectionId,
    type,
    comment,
  });
  return data;
}

export async function getSuggestions(
  text: string,
  strategies: string[]
): Promise<SuggestResult> {
  const { data } = await client.post<SuggestResult>("/suggest", {
    text,
    strategies,
  });
  return data;
}

export async function searchLiterature(
  query: string,
  topK: number = 5
): Promise<{ results: LiteratureItem[] }> {
  const { data } = await client.post<{ results: LiteratureItem[] }>(
    "/research/search",
    { query, top_k: topK }
  );
  return data;
}

export async function getReviewList(
  status?: string
): Promise<{ items: ReviewItem[] }> {
  const { data } = await client.get<{ items: ReviewItem[] }>("/reviews", {
    params: { status },
  });
  return data;
}

export async function submitReview(
  reviewId: string,
  decision: "maintain" | "adjust" | "dismiss",
  comment: string
): Promise<{ success: boolean }> {
  const { data } = await client.post<{ success: boolean }>(
    `/reviews/${reviewId}/decide`,
    { decision, comment }
  );
  return data;
}

export default client;
