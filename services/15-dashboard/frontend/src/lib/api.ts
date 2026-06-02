const API_BASE = '';

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const resp = await fetch(`${API_BASE}${url}`, {
    headers: { 'Content-Type': 'application/json', ...options?.headers },
    ...options,
  });
  if (!resp.ok) {
    const body = await resp.json().catch(() => null);
    throw new Error(body?.meta?.error || `HTTP ${resp.status}`);
  }
  return resp.json();
}

export interface ApiResponse<T = any> {
  data: T;
  meta: { status: string; timestamp: string; total?: number; [key: string]: any };
}

export interface Audit {
  audit_id: string;
  program?: string;
  contract?: string;
  chain?: string;
  state: string;
  priority?: number;
  findings_count?: number;
  critical_count?: number;
  high_count?: number;
  medium_count?: number;
  low_count?: number;
  duration_seconds?: number;
  created_at?: string;
  steps?: any[];
  error?: string;
}

export interface DaemonState {
  status: 'stopped' | 'running' | 'paused' | 'error';
  started_at?: string;
  stopped_at?: string;
  last_run_at?: string;
  next_run_at?: string;
  total_contracts_audited: number;
  total_cycles_completed: number;
  last_error?: string;
}

export interface Program {
  slug: string;
  name?: string;
  max_bounty?: string;
  chains?: string[];
  status?: string;
}

export interface ScopeContract {
  address: string;
  chain: string;
  name: string;
  program_slug: string;
  program_name: string;
  program_max_bounty?: number;
  program_status: string;
}

export interface MetricsSummary {
  total_audits: number;
  total_findings: number;
  critical_findings: number;
  high_findings: number;
  medium_findings: number;
  low_findings: number;
  true_positives: number;
  false_positives: number;
  true_positive_rate: number;
  precision: number;
  recall: number;
  f1_score: number;
  per_tool?: Record<string, any>;
}

export interface PipelineStats {
  total_audits: number;
  completed: number;
  failed: number;
  in_progress: number;
  [key: string]: any;
}

// ── API methods ──

export const api = {
  // Config
  getConfig: () => request<ApiResponse<Record<string, any>>>('/api/config'),
  setConfigKey: (key: string, value: any) =>
    request<ApiResponse>(`/api/config/${key}`, { method: 'PUT', body: JSON.stringify({ value }) }),
  setBulkConfig: (config: Record<string, any>) =>
    request<ApiResponse>('/api/config/bulk', { method: 'PUT', body: JSON.stringify({ config }) }),

  // Audits
  getAudits: (params?: { state?: string; program?: string; chain?: string; limit?: number; offset?: number }) => {
    const qs = new URLSearchParams();
    if (params?.state) qs.set('state', params.state);
    if (params?.program) qs.set('program', params.program);
    if (params?.chain) qs.set('chain', params.chain);
    if (params?.limit) qs.set('limit', String(params.limit));
    if (params?.offset) qs.set('offset', String(params.offset));
    const q = qs.toString();
    return request<ApiResponse<Audit[]>>(`/api/audits${q ? '?' + q : ''}`);
  },
  getAudit: (id: string) => request<ApiResponse<Audit>>(`/api/audits/${id}`),
  startAudit: (body: { chain: string; address: string; program?: string; priority?: number }) =>
    request<ApiResponse>('/api/audit', { method: 'POST', body: JSON.stringify(body) }),
  retryAudit: (id: string) =>
    request<ApiResponse>(`/api/audits/${id}/retry`, { method: 'POST' }),

  // Daemon
  getDaemonStatus: () => request<ApiResponse<DaemonState>>('/api/daemon/status'),
  daemonStart: () => request<ApiResponse>('/api/daemon/start', { method: 'POST' }),
  daemonStop: () => request<ApiResponse>('/api/daemon/stop', { method: 'POST' }),
  daemonSync: () => request<ApiResponse>('/api/daemon/sync', { method: 'POST' }),

  // Programs
  getPrograms: (params?: { search?: string; chain?: string }) => {
    const qs = new URLSearchParams();
    if (params?.search) qs.set('search', params.search);
    if (params?.chain) qs.set('chain', params.chain);
    const q = qs.toString();
    return request<ApiResponse<Program[]>>(`/api/programs${q ? '?' + q : ''}`);
  },
  getProgram: (slug: string) => request<ApiResponse<Program>>(`/api/programs/${slug}`),
  getScopeContracts: (params?: { chain?: string; min_bounty?: number; offset?: number; limit?: number }) => {
    const qs = new URLSearchParams();
    if (params?.chain) qs.set('chain', params.chain);
    if (params?.min_bounty) qs.set('min_bounty', String(params.min_bounty));
    if (params?.offset) qs.set('offset', String(params.offset));
    if (params?.limit) qs.set('limit', String(params.limit));
    const q = qs.toString();
    return request<ApiResponse>(`/api/contracts/scope${q ? '?' + q : ''}`);
  },

  // Stats & Metrics
  getStats: () => request<ApiResponse<PipelineStats>>('/api/stats'),
  getMetrics: () => request<ApiResponse<MetricsSummary>>('/api/metrics'),

  // Feedback
  getFeedback: () => request<ApiResponse<any[]>>('/api/feedback'),
  submitFeedback: (body: { finding_id: string; feedback: string; status: string }) =>
    request<ApiResponse>('/api/feedback', { method: 'POST', body: JSON.stringify(body) }),

  // Notifications
  testNotification: (channel: string) =>
    request<ApiResponse>('/api/notifications/test', { method: 'POST', body: JSON.stringify({ channel }) }),

  // Reports
  generateReport: (auditId: string, format = 'immunefi') =>
    request<ApiResponse>('/api/reports/generate', { method: 'POST', body: JSON.stringify({ audit_id: auditId, format }) }),

  // Queue
  getQueue: () => request<ApiResponse>('/api/queue'),
  addToQueue: (body: { contract_id: string; chain: string; address: string; program?: string; priority_score?: number }) =>
    request<ApiResponse>('/api/queue', { method: 'POST', body: JSON.stringify(body) }),

  // Service Health
  getHealthAll: () => request<ApiResponse<Record<string, {status: string; code?: number; error?: string}>>>('/api/health/all'),
  getHealthGraph: () => request<ApiResponse<{nodes: Record<string, {name: string; status: string; colour: string; latency_ms: number; error: string; timestamp: string}>; edges: Array<{from: string; to: string}>}>>('/api/health/graph'),
  getHealthMetrics: () => request<ApiResponse<{total_services: number; healthy: number; degraded: number; down: number; unknown: number; avg_latency_ms: number; p95_latency_ms: number; error_rate: number; timestamp: string}>>('/api/health/metrics'),

  // Pipeline
  getPipelineStatus: () => request<ApiResponse>('/api/pipeline'),
  getPipelineSteps: () => request<ApiResponse>('/api/pipeline/steps'),

  // Scanner Tools
  getScannerTools: () => request<ApiResponse<Record<string, {status: string}>>>('/api/scanner/tools'),
  getScannerResults: (auditId: string) => request<ApiResponse>(`/api/scanner/${auditId}/results`),

  // Exploit
  getExploitDetail: (findingId: string) => request<ApiResponse>(`/api/exploit/${findingId}`),

  // Notifier
  getNotifierChannels: () => request<ApiResponse>('/api/notifier/channels'),
  getNotifierLogs: (limit = 50) => request<ApiResponse>(`/api/notifier/logs?limit=${limit}`),

  // Webhook
  getWebhookLogs: (limit = 50) => request<ApiResponse>(`/api/webhook/logs?limit=${limit}`),

  // Source
  getSourceCode: (auditId: string) => request<ApiResponse>(`/api/source/${auditId}`),

  // Reports
  getReports: (limit = 50) => request<ApiResponse>(`/api/reports?limit=${limit}`),

  // Upkeep
  getUpkeepStatus: () => request<ApiResponse>('/api/upkeep/status'),
  getUpkeepLogs: (limit = 50) => request<ApiResponse>(`/api/upkeep/logs?limit=${limit}`),

  // Agent
  getAgentHealth: () => request<ApiResponse>('/api/agent/health'),
  getTeamStructure: () => request<ApiResponse>('/api/agent/team/structure'),
  runTeamAudit: (body: { task_type?: string; input_data?: Record<string, any>; goal?: string; max_delegations?: number }) =>
    request<ApiResponse>('/api/agent/team/run', { method: 'POST', body: JSON.stringify(body) }),
  getTeamSessions: (params?: { limit?: number; status?: string }) => {
    const qs = new URLSearchParams();
    if (params?.limit) qs.set('limit', String(params.limit));
    if (params?.status) qs.set('status', params.status);
    const q = qs.toString();
    return request<ApiResponse>(`/api/agent/team/sessions${q ? '?' + q : ''}`);
  },
  getTeamSession: (sessionId: string) => request<ApiResponse>(`/api/agent/team/${sessionId}`),
  getAgentSkills: () => request<ApiResponse>('/api/agent/skills'),
  getAgentSkillMetrics: () => request<ApiResponse>('/api/agent/skills/metrics'),
  getMemoryStats: () => request<ApiResponse>('/api/agent/memory/stats'),
  memorySearch: (query: string, store: string = 'vector') =>
    request<ApiResponse>('/api/agent/memory/search', {
      method: 'POST',
      body: JSON.stringify({ query, store, limit: 20 }),
    }),
  startDaemon: () => request<ApiResponse>('/api/agent/daemon/start', { method: 'POST' }),
  stopDaemon: () => request<ApiResponse>('/api/agent/daemon/stop', { method: 'POST' }),
  getAgentDaemonStatus: () => request<ApiResponse>('/api/agent/daemon/status'),
  sendChatMessage: (message: string, sessionId?: string) =>
    request<ApiResponse>('/api/agent/chat', {
      method: 'POST',
      body: JSON.stringify({ message, session_id: sessionId || null }),
    }),
  submitAgentFeedback: (body: { session_id: string; rating: number; comment?: string; tags?: string[] }) =>
    request<ApiResponse>('/api/agent/learning/feedback', { method: 'POST', body: JSON.stringify(body) }),
  getLearningStats: () => request<ApiResponse>('/api/agent/learning/stats'),
  getLearningRecommendations: (taskType?: string) =>
    request<ApiResponse>(`/api/agent/learning/recommendations${taskType ? `?task_type=${taskType}` : ''}`),

  // ── Submission (Service 16) ─────────────────────────────
  getSubmissions: (params?: { category?: string; status?: string }) => {
    const qs = new URLSearchParams();
    if (params?.category) qs.set('category', params.category);
    if (params?.status) qs.set('status', params.status);
    const q = qs.toString();
    return request<ApiResponse>(`/api/submission${q ? '?' + q : ''}`);
  },
  getSubmission: (findingId: string) => request<ApiResponse>(`/api/submission/${findingId}`),
  createSubmission: (body: {
    finding_id: string; program_slug: string; bug_category: string;
    title: string; description: string; severity: string;
    poc_solidity?: string; tx_hash?: string; exploit_sequence?: string[];
    category_evidence?: Record<string, any>;
  }) => request<ApiResponse>('/api/submission', { method: 'POST', body: JSON.stringify(body) }),
  generateSubmissionDraft: (findingId: string, body: { immunefi_message: string; bug_category?: string; tone?: string }) =>
    request<ApiResponse>(`/api/submission/${findingId}/draft`, { method: 'POST', body: JSON.stringify(body) }),
  respondToImmunefi: (findingId: string, body: { message: string; attachments?: string[] }) =>
    request<ApiResponse>(`/api/submission/${findingId}/respond`, { method: 'POST', body: JSON.stringify(body) }),
  getSubmissionEvidence: (findingId: string) =>
    request<ApiResponse>(`/api/submission/${findingId}/evidence`),
  getSubmissionStats: () => request<ApiResponse>('/api/submission/stats'),
  getSubmissionCategoryStats: () => request<ApiResponse>('/api/submission/stats/categories'),

  // ── Cases (Agenda 05: Each Bug Is Cases) ──────────────
  getCases: (params?: { status?: string; search?: string; severity?: string; confidence?: string; sort?: string; order?: string; limit?: number; offset?: number }) => {
    const qs = new URLSearchParams();
    if (params?.status) qs.set('status', params.status);
    if (params?.search) qs.set('search', params.search);
    if (params?.severity) qs.set('severity', params.severity);
    if (params?.confidence) qs.set('confidence', params.confidence);
    if (params?.sort) qs.set('sort', params.sort);
    if (params?.order) qs.set('order', params.order);
    if (params?.limit) qs.set('limit', String(params.limit));
    if (params?.offset) qs.set('offset', String(params.offset));
    const q = qs.toString();
    return request<ApiResponse<VpCase[]>>(`/api/cases${q ? '?' + q : ''}`);
  },
  getArchive: (params?: { search?: string; sort?: string; order?: string; limit?: number; offset?: number }) => {
    const qs = new URLSearchParams();
    if (params?.search) qs.set('search', params.search);
    if (params?.sort) qs.set('sort', params.sort);
    if (params?.order) qs.set('order', params.order);
    if (params?.limit) qs.set('limit', String(params.limit));
    if (params?.offset) qs.set('offset', String(params.offset));
    const q = qs.toString();
    return request<ApiResponse<VpCase[]>>(`/api/cases/archive${q ? '?' + q : ''}`);
  },
  getCase: (caseId: string) => request<ApiResponse<VpCase>>(`/api/cases/${caseId}`),
  getCaseStats: () => request<ApiResponse<CaseStatsData>>('/api/cases/stats'),
  createCase: (body: {
    project: string; scanners: { name: string; detector: string; confidence: number }[];
    severity?: string; title: string; contract?: string; function?: string; line?: number;
    description?: string; recommendation?: string; proof_of_concept?: string; platform?: string;
  }) => request<ApiResponse<VpCase>>('/api/cases', { method: 'POST', body: JSON.stringify(body) }),
  closeCase: (caseId: string, body: { closed_reason: string; bounty_amount?: number; notes?: string }) =>
    request<ApiResponse<VpCase>>(`/api/cases/${caseId}/close`, { method: 'PUT', body: JSON.stringify(body) }),
  getCaseReportMdUrl: (caseId: string) => `/api/cases/${caseId}/report.md`,
  getCaseReportPdfUrl: (caseId: string) => `/api/cases/${caseId}/report.pdf`,
};

// ── Case Types (Agenda 05) ─────────────────────────────────────
export interface VpScannerFinding {
  name: string;
  detector: string;
  confidence: number;
}

export interface VpCase {
  case_id: string;
  status: 'OPEN' | 'CLOSED';
  project: string;
  scanners: VpScannerFinding[];
  confidence: number;
  confidence_label: string;
  confidence_factors: string[];
  scanner_count: number;
  severity: string;
  title: string;
  contract: string;
  function: string;
  line: number;
  description: string;
  recommendation: string;
  proof_of_concept: string;
  platform: string;
  bounty_amount: number | null;
  notes: string;
  created_at: string;
  closed_at: string | null;
  closed_reason: string | null;
}

export interface CaseStatsData {
  total_cases: number;
  open_cases: number;
  closed_cases: number;
  total_bounty: number;
  avg_confidence: number;
  by_severity: Record<string, number>;
  by_scanner: Record<string, number>;
  label_distribution: Record<string, number>;
  recent_cases: VpCase[];
}
