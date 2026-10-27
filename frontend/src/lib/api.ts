const BASE = import.meta.env.VITE_API_URL ?? '/api'

export type InterviewType = 'technical' | 'behavioural' | 'mixed'
export type Difficulty = 'easy' | 'medium' | 'hard'
export type DocumentKind = 'resume' | 'jd' | 'other'
export type DocumentStatus = 'uploaded' | 'parsing' | 'ready' | 'failed'

export interface Session {
  id: string
  title: string
  target_role: string
  interview_type: InterviewType
  difficulty: Difficulty
  question_count: number
  status: string
  created_at: string
}

export type SessionCreate = Pick<
  Session,
  'title' | 'target_role' | 'interview_type' | 'difficulty' | 'question_count'
>

export interface DocumentItem {
  id: string
  session_id: string
  kind: DocumentKind
  filename: string
  status: DocumentStatus
  error: string | null
  created_at: string
}

export interface DocumentDetail extends DocumentItem {
  raw_text: string | null
  sections_json: Array<{ name: string; text: string }> | null
}

export type SkillLevel = 'beginner' | 'intermediate' | 'advanced' | 'unknown'
export interface SkillItem {
  name: string
  level: SkillLevel
  evidence: string
}
export interface CandidateProfile {
  name: string | null
  total_experience_years: number | null
  current_role: string | null
  skills: SkillItem[]
  employers: Array<{ company: string; role: string; duration: string }>
  projects: Array<{ title: string; tech_stack: string[]; claimed_outcome: string }>
  education: string[]
  certifications: string[]
}
export interface JDRequirements {
  role_title: string | null
  seniority: string
  must_have_skills: string[]
  nice_to_have_skills: string[]
  responsibilities: string[]
  domain: string
  soft_skills: string[]
}
export interface GapAnalysis {
  matched_skills: string[]
  gaps: string[]
  nice_to_have_matched: string[]
  nice_to_have_missing: string[]
  claims_to_probe: Array<{ text: string; reason: string }>
  strengths: string[]
  match_percent: number | null
}
export interface Analysis {
  session_id: string
  status: 'running' | 'ready' | 'failed'
  error: string | null
  model: string | null
  user_edited: boolean
  warnings: string[]
  profile: CandidateProfile | null
  requirements: JDRequirements | null
  gap: GapAnalysis | null
  updated_at: string
}

export type Category = 'intro' | 'core' | 'project' | 'gap' | 'behavioural' | 'closing'
export interface PlanTopic {
  index: number
  category: Category
  topic: string
  difficulty: string
}
export interface Plan {
  session_id: string
  topics: PlanTopic[]
  followup_budget: number
}
export interface Turn {
  question_id: string
  order_no: number
  topic: string
  ack: string
  text: string
  is_follow_up: boolean
  answer: string | null
}
export interface InterviewState {
  session_id: string
  status: string
  main_total: number
  main_asked: number
  turns: Turn[]
}

export type ServerMessage =
  | ({ type: 'state' } & InterviewState)
  | { type: 'thinking' }
  | { type: 'token'; text: string }
  | {
      type: 'question'
      question_id: string
      order_no: number
      topic: string
      text: string
      ack: string
      is_follow_up: boolean
      replay: boolean
      progress: { main_asked: number; main_total: number }
    }
  | { type: 'complete'; message: string }
  | { type: 'error'; message: string; retryable: boolean }

/** WebSocket URL for a backend path, following the same base as REST calls. */
export function wsUrl(path: string): string {
  const base = BASE.startsWith('http') ? BASE : `${window.location.origin}${BASE}`
  return `${base.replace(/^http/, 'ws')}${path}`
}

export type Provider = 'ollama' | 'gemini'
export interface GeminiModel {
  id: string
  label: string
  note: string
  tier: 'free' | 'paid'
}
export interface LLMSettings {
  provider: Provider
  gemini_model: string
  gemini_models: GeminiModel[]
  gemini_key_set: boolean
  gemini_key_hint: string | null
  gemini_key_source: 'settings' | 'environment' | 'none'
  ollama_model: string
}
export interface LLMTestResult {
  ok: boolean
  provider: string
  model: string | null
  seconds: number | null
  message: string
}

export interface DimensionResult {
  score: number
  quote: string
  verified: boolean
}
export interface QuestionReport {
  order_no: number
  topic: string
  category: string
  is_follow_up: boolean
  question: string
  answer: string
  answer_summary: string
  score_percent: number
  dimensions: Record<string, DimensionResult>
  missing_points: string[]
  feedback: string
  sample_answer: string
  notes: string[]
}
export interface ReportBody {
  overall_score: number
  verdict: string
  verdict_basis: string
  target_role: string
  summary: string
  dimension_scores: Record<string, number>
  areas: Array<{ name: string; category: string; score_percent: number; answers: number }>
  strengths: Array<{ title: string; detail: string }>
  improvements: Array<{ title: string; detail: string }>
  questions: QuestionReport[]
  communication: {
    answers: number
    avg_words: number
    shortest_words: number
    longest_words: number
    one_line_answers: number
    rambling_answers: number
    filler_words: Record<string, number>
    vague_phrases: Record<string, number>
    avg_seconds: number | null
    observations: string[]
  }
  improvement_plan: Array<{ timeframe: string; focus: string; actions: string[] }>
  coverage: { planned_topics: number; questions_asked: number; evaluated: number; unanswered: number }
}
export interface Report {
  session_id: string
  status: 'running' | 'ready' | 'failed'
  error: string | null
  model: string | null
  warnings: string[]
  progress_done: number
  progress_total: number
  overall_score: number | null
  report: ReportBody | null
  updated_at: string
}

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(`${BASE}${path}`, init)
  } catch {
    throw new ApiError(0, 'Cannot reach the backend. Is it running on port 8000?')
  }
  if (!res.ok) {
    let message = res.statusText
    try {
      const body = await res.json()
      if (typeof body.detail === 'string') message = body.detail
      else if (Array.isArray(body.detail)) message = body.detail.map((d: { msg: string }) => d.msg).join('; ')
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, message)
  }
  return res.status === 204 ? (undefined as T) : ((await res.json()) as T)
}

const json = (body: unknown): RequestInit => ({
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
})

export const api = {
  listSessions: () => request<Session[]>('/sessions'),
  getSession: (id: string) => request<Session>(`/sessions/${id}`),
  createSession: (payload: SessionCreate) => request<Session>('/sessions', json(payload)),
  deleteSession: (id: string) => request<void>(`/sessions/${id}`, { method: 'DELETE' }),

  listDocuments: (sid: string) => request<DocumentItem[]>(`/sessions/${sid}/documents`),
  getDocument: (sid: string, did: string) => request<DocumentDetail>(`/sessions/${sid}/documents/${did}`),
  uploadDocument: (sid: string, kind: DocumentKind, file: File) => {
    const form = new FormData()
    form.append('kind', kind)
    form.append('file', file)
    return request<DocumentItem>(`/sessions/${sid}/documents`, { method: 'POST', body: form })
  },
  analyze: (sid: string) => request<Analysis>(`/sessions/${sid}/analyze`, { method: 'POST' }),
  /** Resolves to null when no analysis has been started yet. */
  getAnalysis: async (sid: string): Promise<Analysis | null> => {
    try {
      return await request<Analysis>(`/sessions/${sid}/analysis`)
    } catch (e) {
      if (e instanceof ApiError && e.status === 404) return null
      throw e
    }
  },
  patchAnalysis: (sid: string, body: { profile?: CandidateProfile; requirements?: JDRequirements }) =>
    request<Analysis>(`/sessions/${sid}/analysis`, { ...json(body), method: 'PATCH' }),
  getLLMSettings: () => request<LLMSettings>('/settings/llm'),
  saveLLMSettings: (body: { provider: Provider; gemini_model: string; gemini_api_key?: string }) =>
    request<LLMSettings>('/settings/llm', { ...json(body), method: 'PUT' }),
  removeGeminiKey: () => request<LLMSettings>('/settings/llm/key', { method: 'DELETE' }),
  testLLM: () => request<LLMTestResult>('/settings/llm/test', { method: 'POST' }),
  generateReport: (sid: string) => request<Report>(`/sessions/${sid}/report`, { method: 'POST' }),
  /** Resolves to null when no report has been requested yet. */
  getReport: async (sid: string): Promise<Report | null> => {
    try {
      return await request<Report>(`/sessions/${sid}/report`)
    } catch (e) {
      if (e instanceof ApiError && e.status === 404) return null
      throw e
    }
  },
  createPlan: (sid: string) => request<Plan>(`/sessions/${sid}/plan`, { method: 'POST' }),
  getPlan: async (sid: string): Promise<Plan | null> => {
    try {
      return await request<Plan>(`/sessions/${sid}/plan`)
    } catch (e) {
      if (e instanceof ApiError && e.status === 404) return null
      throw e
    }
  },
  getInterview: (sid: string) => request<InterviewState>(`/sessions/${sid}/interview`),
  deleteDocument: (sid: string, did: string) =>
    request<void>(`/sessions/${sid}/documents/${did}`, { method: 'DELETE' }),
}
