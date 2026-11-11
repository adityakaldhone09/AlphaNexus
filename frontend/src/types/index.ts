export interface Company {
  id: string;
  symbol: string;
  name: string;
  exchange: 'NSE' | 'BSE' | string;
  isin?: string;
  sector?: string;
  industry?: string;
  market_cap?: number;
  current_price?: number;
  day_change?: number;
  day_change_percent?: number;
  pe_ratio?: number;
  pb_ratio?: number;
  roe?: number;
  roce?: number;
  dividend_yield?: number;
  week_52_high?: number;
  week_52_low?: number;
  currency: string;
  description?: string;
  website?: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface FinancialMetric {
  id: string;
  company_id: string;
  metric_name: string;
  metric_category: string;
  period_type: string;
  financial_year: string;
  quarter?: string;
  period_end_date: string;
  value: number;
  unit: string;
  currency: string;
  yoy_growth?: number;
  qoq_growth?: number;
  is_consolidated: boolean;
}

export interface DocumentItem {
  id: string;
  company_id: string;
  title: string;
  filename: string;
  file_size_bytes: number;
  mime_type: string;
  financial_year?: string;
  document_type: string;
  status: 'UPLOADED' | 'QUEUED' | 'PROCESSING' | 'PROCESSED' | 'FAILED';
  error_message?: string;
  total_pages: number;
  total_chunks: number;
  created_at: string;
}

export interface CitationItem {
  id?: string;
  document_id?: string;
  document_chunk_id?: string;
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
  role: 'user' | 'assistant' | 'system';
  content: string;
  message_type: 'fact_grounded' | 'calculated' | 'synthesis' | 'user_query';
  tokens_used: number;
  citations: CitationItem[];
  created_at: string;
}

export interface ResearchSession {
  id: string;
  title: string;
  company_id?: string;
  created_at: string;
  updated_at: string;
  messages: ResearchMessage[];
}

export interface NewsArticle {
  id: string;
  company_id?: string;
  title: string;
  description?: string;
  content?: string;
  url: string;
  source: string;
  publisher?: string;
  published_at: string;
  category: string;
  sentiment_label: 'Positive' | 'Negative' | 'Neutral';
  sentiment_score?: number;
  ai_summary?: string;
  financial_impact?: string;
  created_at: string;
}

export interface CorporateAction {
  id: string;
  company_id: string;
  action_type: string;
  details: string;
  ratio_or_amount?: string;
  announcement_date?: string;
  ex_date?: string;
  record_date?: string;
  payment_date?: string;
  status: string;
  source: string;
  created_at: string;
}

export interface MarketEvent {
  id: string;
  company_id: string;
  event_type: string;
  title: string;
  description: string;
  deal_value?: number;
  deal_currency: string;
  counterparty?: string;
  strategic_implications?: string;
  disclosed_date: string;
  source_url?: string;
  created_at: string;
}

export interface ForecastPeriod {
  period: string;
  base: number;
  bullish: number;
  bearish: number;
  confidence_intervals: {
    ci_95: { lower: number; upper: number };
    ci_80: { lower: number; upper: number };
  };
}

export interface ForecastResponseData {
  status: string;
  company_id: string;
  company_symbol: string;
  metric_name: string;
  historical: { period: string; value: number }[];
  forecasts: ForecastPeriod[];
  evaluation?: {
    mae: number;
    rmse: number;
    mape: number;
    directional_accuracy: number;
  };
  disclaimer: string;
}

export interface EngineDetail {
  name: string;
  state: 'Ready' | 'Connected' | 'Configured' | 'Degraded' | 'Disabled' | 'Initializing' | 'Unavailable' | 'Unknown' | 'Failed';
  provider?: string;
  version?: string;
  description?: string;
  details?: string;
  configured?: boolean;
  connected?: boolean | null;
  verified?: boolean;
  latency_ms?: number | null;
  last_successful_operation?: string | null;
  error_category?: string | null;
  error_message?: string | null;
  last_checked: string;
}

export interface EnginesSummary {
  status: string;
  timestamp: string;
  total_engines: number;
  ready_count: number;
  degraded_count: number;
  configured_count?: number;
  unavailable_count?: number;
  disabled_count: number;
  failed_count: number;
  engines: Record<string, EngineDetail>;
}

export interface IntegrationHealth {
  provider: string;
  purpose?: string;
  status: string;
  configured: boolean;
  operational: boolean;
  configured_model?: string | null;
  active_model?: string | null;
  model?: string | null;
  connection_status?: string;
  last_successful_test?: string | null;
  error_category?: string | null;
  error_message?: string | null;
  information?: string;
  latency_ms?: number;
}

export interface IntegrationsHealth {
  timestamp: string;
  total_integrations: number;
  connected_count: number;
  degraded_count: number;
  failed_count: number;
  not_configured_count: number;
  integrations: IntegrationHealth[];
}

export interface SystemConfiguration {
  app_name: string;
  environment: string;
  data_mode: string;
  database: {
    provider: string;
    reachable: boolean;
    fallback: boolean;
  };
  mongodb: {
    configured: boolean;
    database: string | null;
    connected: boolean;
  };
  llm: {
    primary_provider: string | null;
    gemini: { configured: boolean; model: string; fallback_model: string | null };
    groq: { configured: boolean; model: string; fallback_model: string | null };
  };
  embedding: { model: string; dimension: number; device: string; batch_size: number };
  rag: {
    chunk_size: number;
    chunk_overlap: number;
    retrieval_top_k: number;
    hybrid_search_enabled: boolean;
    reranking_enabled: boolean;
  };
  integrations: {
    dhan_configured: boolean;
    marketaux_configured: boolean;
    fmp_configured: boolean;
    supabase_storage_configured: boolean;
  };
}

export interface RAGConfiguration {
  id: string;
  config_version: string;
  is_active: boolean;
  embedding_model: string;
  embedding_dimension: number;
  embedding_batch_size: number;
  embedding_device: string;
  chunk_strategy: string;
  chunk_size: number;
  chunk_overlap: number;
  max_chunk_size: number;
  min_chunk_size: number;
  table_aware_chunking: boolean;
  semantic_chunking: boolean;
  parent_child_chunking: boolean;
  retrieval_top_k: number;
  min_similarity_score: number;
  hybrid_search_enabled: boolean;
  vector_weight: number;
  keyword_weight: number;
  rrf_k: number;
  reranking_enabled: boolean;
  reranking_model: string;
  reranking_top_k: number;
  llm_provider: string;
  llm_model: string;
  llm_temperature: number;
  llm_max_tokens: number;
  require_citations: boolean;
  description?: string | null;
  created_at: string;
  updated_at: string;
}

export interface RAGRetrievalResult {
  query: string;
  rewritten_query: string;
  route: string;
  financial_year_hint: string | null;
  retrieved_count: number;
  routing: Record<string, unknown>;
  chunks: Array<{
    chunk_id: string;
    document_id: string;
    document_title: string;
    document_type: string | null;
    financial_year: string | null;
    filename?: string | null;
    section?: string | null;
    page_number?: number | null;
    content: string;
    similarity_score: number;
    keyword_score: number;
    rerank_score?: number | null;
    rrf_score?: number | null;
    retrieval_method?: string | null;
    metadata?: Record<string, unknown> | null;
  }>;
}

export interface WatchlistItem {
  id: string;
  user_id: string;
  company_id: string;
  target_price?: number;
  alert_threshold_percent?: number;
  notes?: string;
  created_at: string;
  company?: Company;
}
