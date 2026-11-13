import axios from 'axios';
import {
  Company,
  DocumentItem,
  ResearchMessage,
  ResearchSession,
  NewsArticle,
  CorporateAction,
  MarketEvent,
  ForecastResponseData,
  EnginesSummary,
  IntegrationsHealth,
  SystemConfiguration,
  RAGConfiguration,
  RAGRetrievalResult,
  WatchlistItem,
  FinancialMetric,
} from '../types';

const API_BASE = '/api/v1';
const GET_CACHE_TTL_MS = 30_000;

type CachedGet<T> = {
  expiresAt: number;
  promise: Promise<T>;
};

const getCache = new Map<string, CachedGet<unknown>>();
let cacheGeneration = 0;

const stableParams = (params?: object) => {
  if (!params) return '';
  return JSON.stringify(
    Object.fromEntries(Object.entries(params).sort(([left], [right]) => left.localeCompare(right)))
  );
};

const cachedGet = <T>(url: string, params?: object): Promise<T> => {
  const key = `${url}:${stableParams(params)}`;
  const existing = getCache.get(key) as CachedGet<T> | undefined;
  if (existing && existing.expiresAt > Date.now()) return existing.promise;

  const generation = cacheGeneration;
  const request = apiClient.get<T>(url, { params }).then(({ data }) => {
    if (generation === cacheGeneration) {
      getCache.set(key, { expiresAt: Date.now() + GET_CACHE_TTL_MS, promise: request });
    }
    return data;
  }).catch((error: unknown) => {
    if (getCache.get(key)?.promise === request) getCache.delete(key);
    throw error;
  });
  getCache.set(key, { expiresAt: Number.POSITIVE_INFINITY, promise: request });
  return request;
};

export const apiClient = axios.create({
  baseURL: API_BASE,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Response interceptor for clear error surfacing
apiClient.interceptors.response.use(
  (response) => {
    if (response.config.method && response.config.method.toLowerCase() !== 'get') {
      cacheGeneration += 1;
      getCache.clear();
    }
    return response;
  },
  (error) => {
    console.error('API Error:', error.response?.data || error.message);
    return Promise.reject(error);
  }
);

export const api = {
  // Health & Engines
  getHealth: async () => {
    return cachedGet('/health');
  },
  getEngines: async (): Promise<EnginesSummary> => {
    return cachedGet<EnginesSummary>('/health/engines');
  },
  refreshSystemHealth: async (): Promise<{ engines: EnginesSummary; integrations: IntegrationsHealth }> => {
    const { data } = await apiClient.post('/health/refresh', null, { timeout: 90000 });
    return data;
  },
  getEngine: async (engineId: string) => {
    return cachedGet(`/health/engines/${engineId}`);
  },
  getSystemConfiguration: async (): Promise<SystemConfiguration> => {
    return cachedGet('/health/config');
  },
  getDiagnostics: async () => {
    return cachedGet<{ issues: Array<{
      timestamp: string | null;
      severity: string;
      component: string;
      message: string;
      category: string | null;
    }>; count: number }>('/health/diagnostics');
  },
  getIntegrations: async (probe = false): Promise<IntegrationsHealth> => {
    if (probe) {
      const { data } = await apiClient.get('/health/integrations', { params: { probe: true } });
      return data;
    }
    return cachedGet('/health/integrations');
  },
  getRagConfiguration: async (): Promise<RAGConfiguration> => {
    return cachedGet('/rag/config');
  },
  updateRagConfiguration: async (payload: Partial<RAGConfiguration>): Promise<RAGConfiguration> => {
    const { data } = await apiClient.put('/rag/config', payload);
    return data;
  },
  testRagRetrieval: async (payload: {
    query: string;
    top_k: number;
    hybrid: boolean;
    reranking: boolean;
    min_similarity: number;
  }): Promise<RAGRetrievalResult> => {
    const { data } = await apiClient.post('/rag/retrieve', payload);
    return data;
  },

  // Companies
  getCompanies: async (params?: { exchange?: string; sector?: string; search?: string }): Promise<Company[]> => {
    return cachedGet('/companies', params);
  },
  searchCompanies: async (q: string): Promise<Company[]> => {
    return cachedGet('/companies/search', { q });
  },
  getCompany: async (idOrSymbol: string): Promise<Company> => {
    return cachedGet(`/companies/${idOrSymbol}`);
  },
  discoverCompany: async (identifier: string): Promise<Company> => {
    const res = await apiClient.post('/companies/discover', { identifier });
    return res.data;
  },
  syncCompanies: async (): Promise<any> => {
    const res = await apiClient.post('/companies/sync');
    return res.data;
  },
  getCompanyProfile: async (idOrSymbol: string): Promise<any> => {
    return cachedGet(`/companies/${idOrSymbol}/profile`);
  },

  // Documents
  getDocuments: async (params?: { company_id?: string; document_type?: string; status?: string; search?: string }): Promise<DocumentItem[]> => {
    return cachedGet('/documents', params);
  },
  analyzeDocument: async (file: File): Promise<any> => {
    const formData = new FormData();
    formData.append('file', file);
    const res = await apiClient.post('/documents/analyze', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return res.data;
  },
  confirmDocument: async (payload: any): Promise<any> => {
    const res = await apiClient.post('/documents/confirm', payload);
    return res.data;
  },
  uploadDocument: async (formData: FormData): Promise<any> => {
    const res = await apiClient.post('/documents/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return res.data;
  },
  processDocument: async (documentId: string): Promise<any> => {
    const res = await apiClient.post(`/documents/${documentId}/process`);
    return res.data;
  },
  reprocessDocument: async (documentId: string): Promise<any> => {
    const res = await apiClient.post(`/documents/${documentId}/reprocess`);
    return res.data;
  },
  deleteDocument: async (documentId: string): Promise<any> => {
    const res = await apiClient.delete(`/documents/${documentId}`);
    return res.data;
  },

  // AI Research & RAG
  sendResearchChat: async (payload: {
    session_id?: string;
    company_id?: string;
    query: string;
    financial_year?: string;
    document_type?: string;
    top_k?: number;
  }): Promise<ResearchMessage> => {
    const res = await apiClient.post('/research/chat', payload);
    return res.data;
  },
  getResearchSessions: async (): Promise<ResearchSession[]> => {
    return cachedGet('/research/sessions');
  },
  getResearchSession: async (sessionId: string): Promise<ResearchSession> => {
    return cachedGet(`/research/sessions/${sessionId}`);
  },

  // News Intelligence
  getNews: async (params?: { company_id?: string; category?: string; sentiment?: string }): Promise<NewsArticle[]> => {
    return cachedGet('/news', params);
  },
  syncNews: async (): Promise<any> => {
    const res = await apiClient.post('/news/sync');
    return res.data;
  },

  // Financial Analytics
  getCompanyFinancials: async (companyId: string, periodType: string = 'annual'): Promise<FinancialMetric[]> => {
    return cachedGet(`/companies/${companyId}/financials`, { period_type: periodType });
  },
  getCompanyStatements: async (companyId: string, statementType?: string): Promise<any[]> => {
    return cachedGet(`/companies/${companyId}/statements`, { statement_type: statementType });
  },
  getCompanyRatios: async (companyId: string): Promise<{ company_symbol: string; computed_metrics: Record<string, any> }> => {
    return cachedGet(`/companies/${companyId}/ratios`);
  },
  comparePeers: async (companyIds: string[]): Promise<any> => {
    const res = await apiClient.post('/companies/compare', { company_ids: companyIds });
    return res.data;
  },

  // Corporate Actions
  getCorporateActions: async (params?: { company_id?: string; action_type?: string }): Promise<CorporateAction[]> => {
    return cachedGet('/corporate-actions', params);
  },

  // Market Events
  getMarketEvents: async (params?: { company_id?: string; event_type?: string }): Promise<MarketEvent[]> => {
    return cachedGet('/market-events', params);
  },

  // Forecasts
  getForecasts: async (companyId: string, metricName: string = 'revenue'): Promise<ForecastResponseData> => {
    return cachedGet(`/companies/${companyId}/forecasts`, { metric_name: metricName });
  },
  generateForecast: async (companyId: string, payload: { metric_name: string; forecast_horizon_years: number }): Promise<ForecastResponseData> => {
    const res = await apiClient.post(`/companies/${companyId}/forecasts/generate`, payload);
    return res.data;
  },

  // Watchlist
  getWatchlist: async (): Promise<WatchlistItem[]> => {
    return cachedGet('/watchlist');
  },
  addToWatchlist: async (payload: { company_id: string; target_price?: number; notes?: string }): Promise<WatchlistItem> => {
    const res = await apiClient.post('/watchlist', payload);
    return res.data;
  },
  removeFromWatchlist: async (companyId: string): Promise<any> => {
    const res = await apiClient.delete(`/watchlist/${companyId}`);
    return res.data;
  },
};
