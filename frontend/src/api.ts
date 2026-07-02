import type { ApplicationCreate, ConfigPayload, UnderwritingCase, UnstructuredRecord, UnstructuredReviewResponse } from './wire';

export const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '';

type ApiEnvelope<T> = { ok: boolean; data: T };

type ItemsEnvelope<T> = { items: T[] };

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const isFormData = options.body instanceof FormData;
  const headers = isFormData ? (options.headers ?? {}) : { 'Content-Type': 'application/json', ...(options.headers ?? {}) };
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers
  });
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      detail = body.detail ?? detail;
    } catch {
      // keep status text
    }
    throw new Error(detail);
  }
  const envelope = (await response.json()) as ApiEnvelope<T>;
  return envelope.data;
}

export async function getConfig(): Promise<ConfigPayload> {
  return request<ConfigPayload>('/api/config');
}

export async function createApplication(payload: ApplicationCreate): Promise<UnderwritingCase> {
  return request<UnderwritingCase>('/api/applications', { method: 'POST', body: JSON.stringify(payload) });
}

export async function listApplications(status?: string): Promise<UnderwritingCase[]> {
  const query = status ? `?status=${encodeURIComponent(status)}` : '';
  const data = await request<ItemsEnvelope<UnderwritingCase>>(`/api/applications${query}`);
  return data.items;
}

export async function getApplication(id: string): Promise<UnderwritingCase> {
  return request<UnderwritingCase>(`/api/applications/${id}`);
}

export async function uploadUnstructuredFiles(files: File[]): Promise<UnstructuredRecord[]> {
  const form = new FormData();
  files.forEach((file) => form.append('files', file));
  const data = await request<ItemsEnvelope<UnstructuredRecord>>('/api/unstructured-intake/uploads', { method: 'POST', body: form });
  return data.items;
}

export async function listUnstructuredRecords(status?: string): Promise<UnstructuredRecord[]> {
  const query = status ? `?status=${encodeURIComponent(status)}` : '';
  const data = await request<ItemsEnvelope<UnstructuredRecord>>(`/api/unstructured-intake${query}`);
  return data.items;
}

export async function extractUnstructuredRecord(id: string): Promise<UnstructuredRecord> {
  return request<UnstructuredRecord>(`/api/unstructured-intake/${id}/extract`, { method: 'POST', body: '{}' });
}

export async function reviewUnstructuredRecord(
  id: string,
  payload: { action: 'approve' | 'reject'; reviewer: string; notes: string; application?: ApplicationCreate | null }
): Promise<UnstructuredReviewResponse> {
  return request<UnstructuredReviewResponse>(`/api/unstructured-intake/${id}/review`, { method: 'POST', body: JSON.stringify(payload) });
}

export function unstructuredRawUrl(id: string, version?: string): string {
  const cacheKey = version ? `?v=${encodeURIComponent(version)}` : '';
  return `${API_BASE}/api/unstructured-intake/${id}/raw${cacheKey}`;
}

export async function enrichApplication(id: string): Promise<UnderwritingCase> {
  return request<UnderwritingCase>(`/api/applications/${id}/enrich`, { method: 'POST', body: '{}' });
}

export async function underwriteApplication(id: string): Promise<UnderwritingCase> {
  return request<UnderwritingCase>(`/api/applications/${id}/underwrite`, { method: 'POST', body: '{}' });
}

export interface AssignmentRequest { assignee: string }
export interface ReviewDecisionRequest {
  action: 'approve' | 'decline';
  underwriter: string;
  notes: string;
  premium_delta_pct: number;
  deductible_sar?: number | null;
  sublimits: Record<string, number>;
  exclusions: string[];
}
export interface QuoteGenerateRequest { generated_by: string; expiry_days: number }
export interface BindRequest { bound_by: string; accepted_terms: boolean }

export async function listReviews(): Promise<UnderwritingCase[]> {
  const data = await request<ItemsEnvelope<UnderwritingCase>>('/api/reviews');
  return data.items;
}

export async function assignReview(id: string, payload: AssignmentRequest): Promise<UnderwritingCase> {
  return request<UnderwritingCase>(`/api/reviews/${id}/assign`, { method: 'POST', body: JSON.stringify(payload) });
}

export async function decideReview(id: string, payload: ReviewDecisionRequest): Promise<UnderwritingCase> {
  return request<UnderwritingCase>(`/api/reviews/${id}/decision`, { method: 'POST', body: JSON.stringify(payload) });
}

export async function generateQuote(id: string, payload: QuoteGenerateRequest): Promise<UnderwritingCase> {
  return request<UnderwritingCase>(`/api/applications/${id}/quote`, { method: 'POST', body: JSON.stringify(payload) });
}

export async function bindQuote(id: string, payload: BindRequest): Promise<UnderwritingCase> {
  return request<UnderwritingCase>(`/api/quotes/${id}/bind`, { method: 'POST', body: JSON.stringify(payload) });
}

export function quotePdfUrl(id: string): string {
  return `${API_BASE}/api/quotes/${id}/pdf`;
}
