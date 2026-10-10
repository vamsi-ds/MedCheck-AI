/**
 * Central API client for MedCheck AI.
 *
 * Base URL comes from VITE_API_BASE_URL (see .env.example), defaulting to the
 * local backend on port 8001. The auth token is stored in localStorage and
 * attached to every request; the user's role always comes from the server
 * session (GET /api/auth/me) — never from client-side state.
 */

const BASE_URL: string =
  (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/+$/, '') ||
  'http://127.0.0.1:8001'

const TOKEN_KEY = 'medcheck_token'

// ------------------------------------------------------------------ types

export type Role = 'doctor' | 'records_staff' | 'patient' | 'admin'
export type UserStatus = 'pending' | 'active' | 'inactive'

export interface User {
  id: number
  username: string
  email: string
  full_name: string
  role: Role
  status: UserStatus
  patient_id: number | null
  created_at: string
}

export interface TokenResponse {
  access_token: string
  token_type: string
  user: User
}

export interface Patient {
  id: number
  mrn: string
  first_name: string
  last_name: string
  full_name: string
  date_of_birth: string | null
  sex: string | null
  phone: string | null
  email: string | null
  address: string | null
  is_synthetic: boolean
  created_at: string
  open_findings: number
  document_count: number
  visit_count: number
}

export interface PatientList {
  items: Patient[]
  total: number
  page: number
  page_size: number
}

export interface Visit {
  id: number
  patient_id: number
  visit_date: string
  visit_type: string
  department: string
  reason: string
  purpose: string | null
  outcome: string | null
  created_at: string
}

export type ProcessingStatus = 'pending' | 'processing' | 'completed' | 'failed'
export type ExtractionStatus =
  | 'pending'
  | 'succeeded'
  | 'no_text_found'
  | 'ocr_unavailable'
  | 'failed'

export interface DocumentItem {
  id: number
  patient_id: number
  original_filename: string
  document_type: string
  mime_type: string
  file_size: number
  is_synthetic: boolean
  processing_status: ProcessingStatus
  extraction_status: ExtractionStatus
  extraction_error: string | null
  uploaded_at: string
  document_date: string | null
  uploaded_by_username: string | null
}

export interface DocumentDetail extends DocumentItem {
  extracted_text_preview: string | null
  extracted_char_count: number | null
  extraction_method: string | null
}

export interface DocumentStatus {
  id: number
  processing_status: ProcessingStatus
  extraction_status: ExtractionStatus
  extraction_error: string | null
}

export type FindingCategory = 'allergy' | 'medication' | 'diagnosis' | 'demographic'
export type Severity = 'low' | 'medium' | 'high'
export type FindingStatus = 'needs_review' | 'verified' | 'dismissed' | 'escalated'

export interface FindingSource {
  id: number
  document_id: number
  excerpt: string
  match_reason: string
  document_date: string | null
  document_filename: string | null
}

export interface FindingReview {
  id: number
  reviewer_user_id: number
  reviewer_name: string | null
  decision: FindingStatus
  reason: string
  created_at: string
}

export interface Finding {
  id: number
  patient_id: number
  category: FindingCategory
  severity: Severity
  title: string
  description: string
  explanation: string
  status: FindingStatus
  rule_key: string
  confidence: number
  source_a_document_id: number
  source_b_document_id: number
  source_a_filename: string | null
  source_b_filename: string | null
  source_a_date: string | null
  source_b_date: string | null
  created_at: string
  updated_at: string
  sources: FindingSource[]
  reviews: FindingReview[]
}

export interface AnalyticsSummary {
  patient_count: number
  visit_count: number
  document_count: number
  pending_documents: number
  failed_documents: number
  finding_count: number
  findings_needs_review: number
  findings_verified: number
  findings_disclaimed: number
  findings_escalated: number
  findings_by_category: Record<string, number>
  findings_by_severity: Record<string, number>
  user_count: number
  pending_users: number
}

export interface AuditEvent {
  id: number
  actor_user_id: number | null
  actor_username: string | null
  action: string
  entity_type: string | null
  entity_id: string | null
  detail: string | null
  created_at: string
}

export interface RegisterRequest {
  username: string
  email: string
  full_name: string
  password: string
  role: 'doctor' | 'records_staff' | 'patient'
}

// ------------------------------------------------------------- token store

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token: string | null): void {
  if (token) localStorage.setItem(TOKEN_KEY, token)
  else localStorage.removeItem(TOKEN_KEY)
}

// ---------------------------------------------------------------- requests

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string> | undefined),
  }
  const token = getToken()
  if (token) headers.Authorization = `Bearer ${token}`
  if (options.body && !(options.body instanceof FormData)) {
    headers['Content-Type'] = 'application/json'
  }

  let response: Response
  try {
    response = await fetch(`${BASE_URL}${path}`, { ...options, headers })
  } catch {
    throw new ApiError(0, 'Cannot reach the backend. Is it running on ' + BASE_URL + '?')
  }

  if (response.status === 401) {
    // Invalid/expired token: clear it so the login screen appears.
    setToken(null)
  }
  if (!response.ok) {
    let detail = `Request failed (${response.status})`
    try {
      const body = await response.json()
      if (typeof body.detail === 'string') detail = body.detail
      else if (Array.isArray(body.detail) && body.detail[0]?.msg)
        detail = String(body.detail[0].msg)
    } catch {
      /* keep default message */
    }
    throw new ApiError(response.status, detail)
  }
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

// ------------------------------------------------------------------- auth

export const api = {
  health: () => request<{ status: string; database: string; ocr_available: boolean; version: string }>('/api/health'),

  async login(username: string, password: string): Promise<TokenResponse> {
    const res = await request<TokenResponse>('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    })
    setToken(res.access_token)
    return res
  },

  register: (payload: RegisterRequest) =>
    request<User>('/api/auth/register', { method: 'POST', body: JSON.stringify(payload) }),

  me: () => request<User>('/api/auth/me'),

  logout: () => setToken(null),

  // ------------------------------------------------------------- patients

  listPatients: (opts: { q?: string; page?: number; page_size?: number } = {}) => {
    const params = new URLSearchParams()
    if (opts.q) params.set('q', opts.q)
    if (opts.page) params.set('page', String(opts.page))
    if (opts.page_size) params.set('page_size', String(opts.page_size))
    const qs = params.toString()
    return request<PatientList>(`/api/patients${qs ? `?${qs}` : ''}`)
  },

  getPatient: (id: number) => request<Patient>(`/api/patients/${id}`),

  createPatient: (payload: {
    first_name: string
    last_name: string
    date_of_birth?: string | null
    sex?: string | null
    phone?: string | null
    email?: string | null
    address?: string | null
  }) => request<Patient>('/api/patients', { method: 'POST', body: JSON.stringify(payload) }),

  updatePatient: (id: number, payload: Record<string, unknown>) =>
    request<Patient>(`/api/patients/${id}`, { method: 'PATCH', body: JSON.stringify(payload) }),

  requestCorrection: (patientId: number, message: string) =>
    request<void>(`/api/patients/${patientId}/correction-requests`, {
      method: 'POST',
      body: JSON.stringify({ message }),
    }),

  // -------------------------------------------------------------- visits

  listVisits: (patientId: number) => request<Visit[]>(`/api/patients/${patientId}/visits`),

  createVisit: (patientId: number, payload: Record<string, unknown>) =>
    request<Visit>(`/api/patients/${patientId}/visits`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  // ----------------------------------------------------------- documents

  listDocuments: (patientId: number) =>
    request<DocumentItem[]>(`/api/patients/${patientId}/documents`),

  uploadDocument: (
    patientId: number,
    file: File,
    documentType: string,
    documentDate: string | null,
  ) => {
    const form = new FormData()
    form.append('file', file)
    form.append('document_type', documentType)
    if (documentDate) form.append('document_date', documentDate)
    return request<DocumentItem>(`/api/patients/${patientId}/documents`, {
      method: 'POST',
      body: form,
    })
  },

  getDocument: (id: number) => request<DocumentDetail>(`/api/documents/${id}`),

  getDocumentStatus: (id: number) => request<DocumentStatus>(`/api/documents/${id}/status`),

  updateDocumentMetadata: (id: number, payload: { document_type?: string; document_date?: string | null }) =>
    request<DocumentItem>(`/api/documents/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }),

  // ------------------------------------------------------------ findings

  listFindings: (patientId: number, status?: FindingStatus) =>
    request<Finding[]>(
      `/api/patients/${patientId}/findings${status ? `?finding_status=${status}` : ''}`,
    ),

  getFinding: (id: number) => request<Finding>(`/api/findings/${id}`),

  reviewFinding: (id: number, decision: 'verified' | 'dismissed' | 'escalated', reason: string) =>
    request<Finding>(`/api/findings/${id}/review`, {
      method: 'PATCH',
      body: JSON.stringify({ decision, reason }),
    }),

  analyzePatient: (patientId: number) =>
    request<Finding[]>(`/api/patients/${patientId}/analyze`, { method: 'POST' }),

  // ----------------------------------------------------------- analytics

  analyticsSummary: () => request<AnalyticsSummary>('/api/analytics/summary'),

  // --------------------------------------------------------------- admin

  adminListUsers: (status?: UserStatus) =>
    request<User[]>(`/api/admin/users${status ? `?user_status=${status}` : ''}`),

  adminUpdateUser: (id: number, payload: { status?: UserStatus; role?: Role }) =>
    request<User>(`/api/admin/users/${id}`, { method: 'PATCH', body: JSON.stringify(payload) }),

  adminListAudit: (page = 1) => request<AuditEvent[]>(`/api/admin/audit?page=${page}`),
}
