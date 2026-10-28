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
  overall_score: number | null
  focus_topics: string[] | null
  practice_mode?: 'live' | 'mcq'
}

export type SessionCreate = Pick<
  Session,
  'title' | 'target_role' | 'interview_type' | 'difficulty' | 'question_count' | 'practice_mode'
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
export interface ReusableDocument { id: string; filename: string; session_title: string; kind: 'resume' | 'jd' }

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

export interface MCQQuestion {
  question_id: string
  order_no: number
  topic: string
  text: string
  options: string[]
  selected_index: number | null
  correct: boolean | null
  correct_index: number | null
  explanation: string | null
}
export interface MCQState {
  session_id: string
  status: string
  total: number
  answered: number
  score: number | null
  current: MCQQuestion | null
  results: MCQQuestion[]
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

export type Provider = 'ollama' | 'gemini' | 'openai' | 'anthropic' | 'azure'
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
  ollama_enabled: boolean
  openai_model: string
  anthropic_model: string
  azure_model: string
  azure_endpoint: string
  azure_api_version: string
  key_set: Record<string, boolean>
  key_hint: Record<string, string | null>
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
    voice: { answers: number; avg_wpm: number | null; total_pauses: number; avg_pauses: number; longest_pause: number } | null
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

export interface User {
  id: string
  email: string
  name: string
  created_at: string
}

export interface DashboardStats {
  interviews: number
  finished: number
  reports: number
  avg_score: number | null
  best_score: number | null
  latest_score: number | null
  change: number | null
  streak_days: number
  practice_days_30: number
  answers: number
}
export interface TopicStat {
  name: string
  score: number
  attempts: number
}
export interface Dashboard {
  stats: DashboardStats
  trend: Array<{ session_id: string; title: string; target_role: string; date: string; score: number }>
  weakest: TopicStat[]
  strongest: TopicStat[]
  dimensions: Array<{ key: string; label: string; score: number; change: number | null }>
  next_action: { kind: 'new' | 'upload' | 'analyse' | 'plan' | 'start' | 'continue' | 'report'; title: string | null; label: string; description: string; session_id: string | null; href: string }
  recent: Array<{ session_id: string; title: string; status: string; score: number | null; at: string }>
  badges: Array<{ id: string; label: string; description: string; earned: boolean }>
}

export interface VoiceStatus {
  stt: { available: boolean; model: string; loaded: boolean; hint: string | null }
  tts: { available: boolean; voice: string; hint: string | null }
}
export interface Transcript {
  text: string
  seconds: number
  words: number
  wpm: number | null
  pauses: number
  longest_pause: number
  fillers: number
}
export type VoiceMetrics = Pick<Transcript, 'seconds' | 'words' | 'wpm' | 'pauses' | 'longest_pause' | 'fillers'>

export interface HistoryItem {
  session_id: string
  title: string
  target_role: string
  created_at: string
  overall_score: number
  verdict: string
  evaluated: number
}
export interface DeltaRow {
  name: string
  a: number | null
  b: number | null
  delta: number | null
}
export interface Attempt {
  session_id: string
  title: string
  target_role: string
  created_at: string
  overall_score: number
  verdict: string
  avg_words: number
}
export interface Comparison {
  a: Attempt
  b: Attempt
  overall_delta: number
  dimensions: DeltaRow[]
  areas: DeltaRow[]
  same_role: boolean
}
export interface DataSummary {
  sessions: number
  documents: number
  answers: number
  reports: number
  upload_bytes: number
}
export interface CodingStatus { enabled: boolean; languages: string[]; max_code_chars: number; timeout_seconds: number }
export interface CodeResult { exit_code: number | null; stdout: string; stderr: string; timed_out: boolean }
export interface BankQuestion { question: string; category: string; difficulty: 'easy' | 'medium' | 'hard' }
export interface QuestionBank { id: string; name: string; company: string; notes: string; questions_json: BankQuestion[]; created_at: string; updated_at: string }
export interface DesignFeedback { strengths: string[]; risks: string[]; follow_up_questions: string[]; summary: string }
export interface SystemDesign { id: string; title: string; prompt: string; notes: string; filename: string; media_type: string; feedback_json: DesignFeedback | null; created_at: string }

export const speakUrl = () => `${BASE}/voice/speak`

export const reportPdfUrl = (sid: string) => `${BASE}/sessions/${sid}/report/pdf`

export const AUTH_EXPIRED = 'auth:expired'

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
    res = await fetch(`${BASE}${path}`, { credentials: 'include', ...init })
  } catch {
    throw new ApiError(0, 'Cannot reach the backend. Is it running on port 8000?')
  }
  if (res.status === 401 && !path.startsWith('/auth/login') && !path.startsWith('/auth/signup') && !path.startsWith('/auth/me')) {
    // The session ended (expired, signed out elsewhere, password changed): let the app send the user to the login page.
    window.dispatchEvent(new Event(AUTH_EXPIRED))
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
  authConfig: () => request<{ allow_signup: boolean }>('/auth/config'),
  /** Resolves to null when nobody is signed in. */
  me: async (): Promise<User | null> => {
    try {
      return await request<User>('/auth/me')
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) return null
      throw e
    }
  },
  signup: (body: { email: string; name: string; password: string }) => request<User>('/auth/signup', json(body)),
  login: (body: { email: string; password: string }) => request<User>('/auth/login', json(body)),
  logout: () => request<void>('/auth/logout', { method: 'POST' }),
  changePassword: (body: { current_password: string; new_password: string }) => request<void>('/auth/change-password', json(body)),
  deleteAccount: (password: string) =>
    request<void>('/auth/me', { method: 'DELETE', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ password }) }),

  listSessions: () => request<Session[]>('/sessions'),
  getSession: (id: string) => request<Session>(`/sessions/${id}`),
  createSession: (payload: SessionCreate) => request<Session>('/sessions', json(payload)),
  deleteSession: (id: string) => request<void>(`/sessions/${id}`, { method: 'DELETE' }),
  getMCQ: (sid: string) => request<MCQState>(`/sessions/${sid}/mcq`),
  startMCQ: (sid: string) => request<MCQState>(`/sessions/${sid}/mcq/start`, { method: 'POST' }),
  answerMCQ: (sid: string, question_id: string, selected_index: number) => request<MCQState>(`/sessions/${sid}/mcq/answer`, json({ question_id, selected_index })),

  listDocuments: (sid: string) => request<DocumentItem[]>(`/sessions/${sid}/documents`),
  reusableDocuments: (sid: string) => request<ReusableDocument[]>(`/sessions/${sid}/documents/reuse-options`),
  reuseDocument: (sid: string, document_id: string) => request<DocumentItem>(`/sessions/${sid}/documents/reuse`, json({ document_id })),
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
  saveLLMSettings: (body: { provider: Provider; gemini_model: string; gemini_api_key?: string; api_key?: string; model?: string; azure_endpoint?: string; azure_api_version?: string }) =>
    request<LLMSettings>('/settings/llm', { ...json(body), method: 'PUT' }),
  removeGeminiKey: () => request<LLMSettings>('/settings/llm/key', { method: 'DELETE' }),
  removeProviderKey: (provider: Exclude<Provider, 'ollama'>) => request<LLMSettings>(`/settings/llm/key/${provider}`, { method: 'DELETE' }),
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
  dashboard: () => request<Dashboard>('/dashboard'),
  retry: (sid: string, focus: 'same' | 'weak', topics?: string[]) =>
    request<Session>(`/sessions/${sid}/retry`, json({ focus, ...(topics && topics.length ? { topics } : {}) })),
  weakTopics: (sid: string) => request<string[]>(`/sessions/${sid}/weak-topics`),
  voiceStatus: () => request<VoiceStatus>('/voice/status'),
  transcribe: (audio: Blob, sessionId?: string) => {
    const form = new FormData()
    form.append('file', audio, 'answer.webm')
    if (sessionId) form.append('session_id', sessionId)
    return request<Transcript>('/voice/transcribe', { method: 'POST', body: form })
  },
  getHistory: () => request<HistoryItem[]>('/history'),
  compare: (a: string, b: string) => request<Comparison>(`/history/compare?a=${encodeURIComponent(a)}&b=${encodeURIComponent(b)}`),
  getDataSummary: () => request<DataSummary>('/data'),
  deleteAllData: () =>
    request<DataSummary>('/data', { method: 'DELETE', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ confirm: 'DELETE ALL' }) }),
  codingStatus: () => request<CodingStatus>('/labs/coding'),
  runCode: (language: string, code: string, stdin = '') => request<CodeResult>('/labs/coding/run', json({ language, code, stdin })),
  listQuestionBanks: () => request<QuestionBank[]>('/labs/question-banks'),
  createQuestionBank: (body: { name: string; company: string; notes: string }) => request<QuestionBank>('/labs/question-banks', json(body)),
  generateQuestionBank: (id: string, count: number) => request<QuestionBank>(`/labs/question-banks/${id}/generate`, json({ count })),
  deleteQuestionBank: (id: string) => request<void>(`/labs/question-banks/${id}`, { method: 'DELETE' }),
  listSystemDesigns: () => request<SystemDesign[]>('/labs/system-designs'),
  createSystemDesign: (body: { title: string; prompt: string; notes: string; diagram: File }) => {
    const form = new FormData()
    form.append('title', body.title)
    form.append('prompt', body.prompt)
    form.append('notes', body.notes)
    form.append('diagram', body.diagram)
    return request<SystemDesign>('/labs/system-designs', { method: 'POST', body: form })
  },
  deleteSystemDesign: (id: string) => request<void>(`/labs/system-designs/${id}`, { method: 'DELETE' }),
  reviewSystemDesign: (id: string) => request<SystemDesign>(`/labs/system-designs/${id}/review`, { method: 'POST' }),
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

export const systemDesignDiagramUrl = (id: string) => `${BASE}/labs/system-designs/${id}/diagram`
