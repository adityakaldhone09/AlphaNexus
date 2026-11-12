// AlphaNexus — Research Workspace Types

export type ResearchMode =
  | 'quick'
  | 'deep'
  | 'live'
  | 'document'
  | 'comparative'
  | 'event';

export interface ResearchModeConfig {
  id: ResearchMode;
  label: string;
  description: string;
  icon: string;
  estimatedTime: string;
  toolsUsed: string[];
}

export const RESEARCH_MODES: ResearchModeConfig[] = [
  {
    id: 'quick',
    label: 'Quick Research',
    description: 'Fast answers with key facts and citations',
    icon: '⚡',
    estimatedTime: '5–15s',
    toolsUsed: ['Database', 'Live Data'],
  },
  {
    id: 'deep',
    label: 'Deep Research',
    description: 'Comprehensive multi-source analysis with full report',
    icon: '🔬',
    estimatedTime: '20–45s',
    toolsUsed: ['Database', 'Live Data', 'Documents', 'Calculations'],
  },
  {
    id: 'live',
    label: 'Live Intelligence',
    description: 'Latest exchange announcements, news, and corporate actions',
    icon: '📡',
    estimatedTime: '10–20s',
    toolsUsed: ['Announcements', 'News', 'Corporate Actions'],
  },
  {
    id: 'document',
    label: 'Document Research',
    description: 'Answer grounded in uploaded filings with page references',
    icon: '📄',
    estimatedTime: '8–20s',
    toolsUsed: ['RAG Retrieval', 'Database'],
  },
  {
    id: 'comparative',
    label: 'Comparative',
    description: 'Side-by-side analysis of multiple companies',
    icon: '⚖️',
    estimatedTime: '20–40s',
    toolsUsed: ['Database', 'Live Data', 'Calculations'],
  },
  {
    id: 'event',
    label: 'Event Analysis',
    description: 'Analyze corporate announcements and business events',
    icon: '📌',
    estimatedTime: '15–30s',
    toolsUsed: ['Announcements', 'News', 'Database'],
  },
];

export interface AgentActivityEvent {
  stage: string;
  message: string;
  tool?: string;
  status?: 'ok' | 'success' | 'unavailable' | 'skipped';
  is_live?: boolean;
  elapsed_ms?: number;
  timestamp?: string;
}

export interface ResearchSource {
  label: string;
  type: 'live' | 'database' | 'document' | 'news';
  retrieved_at?: string;
}

export interface ResearchCitation {
  document_id?: string;
  document_title?: string;
  page_number?: number;
  section?: string;
  excerpt: string;
  source_url?: string;
  confidence_score: number;
}

export interface ResearchMessage {
  id: string;
  session_id: string;
  role: 'user' | 'assistant';
  content: string;
  message_type: string;
  tokens_used?: number;
  citations?: ResearchCitation[];
  created_at: string;
  // Agent-specific fields
  tools_used?: string[];
  sources?: string[];
  research_mode?: ResearchMode;
  answer_type?: string;
  activity_log?: AgentActivityEvent[];
  started_at?: string;
  completed_at?: string;
}

export interface ResearchSession {
  id: string;
  title: string;
  company_id?: string;
  company_symbol?: string;
  created_at: string;
  updated_at: string;
  messages?: ResearchMessage[];
}

export interface AgentResearchRequest {
  query: string;
  research_mode: ResearchMode;
  company_symbol?: string;
  company_id?: string;
  financial_year?: string;
  document_type?: string;
  session_id?: string;
}

export interface AgentResearchResponse {
  session_id: string;
  message_id: string;
  query: string;
  answer: string;
  answer_type: string;
  research_mode: string;
  company?: string;
  tools_used: string[];
  sources: string[];
  started_at?: string;
  completed_at?: string;
  citations?: ResearchCitation[];
}

export interface AgentStatus {
  status: 'ready' | 'degraded';
  tools_available: string[];
  llm_configured: boolean;
  llm_provider?: string;
  indianapi_configured: boolean;
  marketaux_configured: boolean;
  rag_available: boolean;
}

// SSE event types
export type SSEEventType = 'activity' | 'answer' | 'sources' | 'done' | 'error' | 'persisted';

export interface SSEActivityEvent {
  stage: string;
  message: string;
  tool?: string;
  status?: string;
  is_live?: boolean;
  elapsed_ms?: number;
  timestamp?: string;
  session_id?: string;
}

export interface SSEAnswerEvent {
  content: string;
  answer_type: string;
  mode: string;
  company?: string;
  session_id: string;
  started_at?: string;
  completed_at?: string;
}

export interface SSESourcesEvent {
  sources: string[];
  evidence_count: number;
  tools_used: string[];
  session_id?: string;
}

export interface SSEDoneEvent {
  completed: boolean;
  tools_used: string[];
  sources_count: number;
  has_answer: boolean;
  session_id?: string;
}
