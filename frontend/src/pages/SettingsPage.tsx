import React, { useState } from 'react';
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  CircleHelp,
  Clock3,
  Cpu,
  Database,
  FileStack,
  HardDrive,
  HeartPulse,
  LoaderCircle,
  Moon,
  PlugZap,
  RefreshCw,
  Save,
  Search,
  Server,
  Settings2,
  ShieldAlert,
  Sparkles,
  Sun,
  Terminal,
  XCircle,
} from 'lucide-react';
import { Badge } from '../components/ui/Badge';
import { Button } from '../components/ui/Button';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/Card';
import { api } from '../services/api';
import { useThemeStore } from '../stores/themeStore';
import {
  EngineDetail,
  EnginesSummary,
  IntegrationHealth,
  IntegrationsHealth,
  RAGConfiguration,
  RAGRetrievalResult,
  SystemConfiguration,
} from '../types';

type SettingsTab =
  | 'overview'
  | 'engines'
  | 'ai-rag'
  | 'integrations'
  | 'database'
  | 'preferences'
  | 'diagnostics';

interface BasicHealth {
  status: string;
  environment: string;
  data_mode: string;
  timestamp: string;
  database_connected: boolean;
}

interface DiagnosticIssue {
  timestamp: string | null;
  severity: string;
  component: string;
  message: string;
  category: string | null;
}

interface Diagnostics {
  issues: DiagnosticIssue[];
  count: number;
}

const tabs: Array<{ id: SettingsTab; label: string; icon: React.ElementType }> = [
  { id: 'overview', label: 'System Overview', icon: Activity },
  { id: 'engines', label: 'Engine Health', icon: Cpu },
  { id: 'ai-rag', label: 'AI & RAG', icon: Sparkles },
  { id: 'integrations', label: 'Integrations', icon: PlugZap },
  { id: 'database', label: 'Database & Storage', icon: Database },
  { id: 'preferences', label: 'Preferences', icon: Settings2 },
  { id: 'diagnostics', label: 'Logs & Diagnostics', icon: Terminal },
];

const surfaceStyle: React.CSSProperties = {
  background: 'var(--surface-1)',
  borderColor: 'var(--border)',
  color: 'var(--text-1)',
};

const fieldStyle: React.CSSProperties = {
  background: 'var(--surface-2)',
  borderColor: 'var(--border-strong)',
  color: 'var(--text-1)',
};

const detailStyle: React.CSSProperties = { color: 'var(--text-2)' };

function errorText(error: unknown): string {
  return error instanceof Error ? error.message : 'An unexpected error occurred.';
}

function formatTime(value?: string | null): string {
  if (!value) return 'Not yet verified';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? 'Unknown' : date.toLocaleString();
}

function statusTone(status: string): 'gain' | 'warning' | 'loss' | 'neutral' {
  if (['Ready', 'Connected', 'Operational'].includes(status)) return 'gain';
  if (['Degraded', 'Configured', 'Initializing'].includes(status)) return 'warning';
  if (['Critical', 'Unavailable', 'Failed'].includes(status)) return 'loss';
  return 'neutral';
}

function StatusBadge({ status }: { status: string }) {
  const Icon =
    statusTone(status) === 'gain'
      ? CheckCircle2
      : statusTone(status) === 'warning'
        ? AlertTriangle
        : statusTone(status) === 'loss'
          ? XCircle
          : CircleHelp;
  return (
    <Badge variant={statusTone(status)} size="sm">
      <Icon className="mr-1 h-3.5 w-3.5" />
      {status}
    </Badge>
  );
}

function MetricCard({
  label,
  value,
  note,
  icon: Icon,
  tone,
}: {
  label: string;
  value: string | number;
  note: string;
  icon: React.ElementType;
  tone?: string;
}) {
  return (
    <Card className="p-4 sm:p-5" style={surfaceStyle}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-xs font-medium uppercase tracking-wide" style={detailStyle}>{label}</div>
          <div className="mt-2 text-2xl font-bold font-tabular" style={{ color: tone || 'var(--text-1)' }}>{value}</div>
          <div className="mt-1 text-xs" style={detailStyle}>{note}</div>
        </div>
        <span className="rounded-lg p-2" style={{ color: 'var(--brand)', background: 'var(--brand-muted)' }}>
          <Icon className="h-4 w-4" />
        </span>
      </div>
    </Card>
  );
}

function SectionCard({
  title,
  description,
  children,
}: {
  title: string;
  description?: string;
  children: React.ReactNode;
}) {
  return (
    <Card style={surfaceStyle}>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        {description && <p className="mt-1 text-xs" style={detailStyle}>{description}</p>}
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  );
}

export const SettingsPage: React.FC = () => {
  const { theme, toggleTheme } = useThemeStore();
  const [activeTab, setActiveTab] = useState<SettingsTab>('overview');
  const [engineSummary, setEngineSummary] = useState<EnginesSummary | null>(null);
  const [health, setHealth] = useState<BasicHealth | null>(null);
  const [configuration, setConfiguration] = useState<SystemConfiguration | null>(null);
  const [integrations, setIntegrations] = useState<IntegrationsHealth | null>(null);
  const [diagnostics, setDiagnostics] = useState<Diagnostics | null>(null);
  const [ragConfig, setRagConfig] = useState<RAGConfiguration | null>(null);
  const [ragResult, setRagResult] = useState<RAGRetrievalResult | null>(null);
  const [ragQuery, setRagQuery] = useState('');
  const [ragError, setRagError] = useState<string | null>(null);
  const [pageError, setPageError] = useState<string | null>(null);
  const [ragLoadError, setRagLoadError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [isLoadingRag, setIsLoadingRag] = useState(false);
  const [isSavingRag, setIsSavingRag] = useState(false);
  const [isTestingRag, setIsTestingRag] = useState(false);
  const [ragSaved, setRagSaved] = useState(false);

  React.useEffect(() => {
    let active = true;
    const load = async () => {
      setIsLoading(true);
      setPageError(null);
      const results = await Promise.allSettled([
        api.getEngines(),
        api.getHealth(),
        api.getIntegrations(),
        api.getSystemConfiguration(),
        api.getDiagnostics(),
      ]);
      if (!active) return;
      const errors: string[] = [];
      const [enginesResult, healthResult, integrationsResult, configurationResult, diagnosticsResult] = results;
      if (enginesResult.status === 'fulfilled') setEngineSummary(enginesResult.value);
      else errors.push(`Engine health: ${errorText(enginesResult.reason)}`);
      if (healthResult.status === 'fulfilled') setHealth(healthResult.value as BasicHealth);
      else errors.push(`Backend health: ${errorText(healthResult.reason)}`);
      if (integrationsResult.status === 'fulfilled') setIntegrations(integrationsResult.value);
      else errors.push(`Integrations: ${errorText(integrationsResult.reason)}`);
      if (configurationResult.status === 'fulfilled') setConfiguration(configurationResult.value);
      else errors.push(`Configuration: ${errorText(configurationResult.reason)}`);
      if (diagnosticsResult.status === 'fulfilled') setDiagnostics(diagnosticsResult.value);
      else errors.push(`Diagnostics: ${errorText(diagnosticsResult.reason)}`);
      if (errors.length) setPageError(errors.join(' '));
      setIsLoading(false);
    };
    void load();
    return () => { active = false; };
  }, []);

  const loadRagConfiguration = async () => {
    if (ragConfig || isLoadingRag) return;
    setIsLoadingRag(true);
    setRagLoadError(null);
    try {
      setRagConfig(await api.getRagConfiguration());
    } catch (error) {
      setRagLoadError(`Unable to load persisted RAG settings: ${errorText(error)}`);
    } finally {
      setIsLoadingRag(false);
    }
  };

  const refreshHealth = async () => {
    setIsRefreshing(true);
    setPageError(null);
    try {
      const result = await api.refreshSystemHealth();
      setEngineSummary(result.engines);
      setIntegrations(result.integrations);
      const [healthResult, diagnosticsResult, configurationResult] = await Promise.allSettled([
        api.getHealth(),
        api.getDiagnostics(),
        api.getSystemConfiguration(),
      ]);
      if (healthResult.status === 'fulfilled') setHealth(healthResult.value as BasicHealth);
      if (diagnosticsResult.status === 'fulfilled') setDiagnostics(diagnosticsResult.value);
      if (configurationResult.status === 'fulfilled') setConfiguration(configurationResult.value);
      const failed = [healthResult, diagnosticsResult, configurationResult]
        .filter((item) => item.status === 'rejected');
      if (failed.length) setPageError('Health checks completed, but some supplementary status could not be refreshed.');
    } catch (error) {
      setPageError(`System health refresh failed: ${errorText(error)}`);
    } finally {
      setIsRefreshing(false);
    }
  };

  const saveRagConfiguration = async () => {
    if (!ragConfig) return;
    setIsSavingRag(true);
    setRagSaved(false);
    setRagLoadError(null);
    try {
      const saved = await api.updateRagConfiguration({
        chunk_size: ragConfig.chunk_size,
        chunk_overlap: ragConfig.chunk_overlap,
        retrieval_top_k: ragConfig.retrieval_top_k,
        min_similarity_score: ragConfig.min_similarity_score,
        hybrid_search_enabled: ragConfig.hybrid_search_enabled,
        vector_weight: ragConfig.vector_weight,
        keyword_weight: ragConfig.keyword_weight,
        reranking_enabled: ragConfig.reranking_enabled,
        reranking_model: ragConfig.reranking_model,
        reranking_top_k: ragConfig.reranking_top_k,
        llm_provider: ragConfig.llm_provider,
        llm_model: ragConfig.llm_model,
        llm_temperature: ragConfig.llm_temperature,
        llm_max_tokens: ragConfig.llm_max_tokens,
        description: ragConfig.description ?? undefined,
      });
      setRagConfig(saved);
      setRagSaved(true);
    } catch (error) {
      setRagLoadError(`Unable to save RAG settings: ${errorText(error)}`);
    } finally {
      setIsSavingRag(false);
    }
  };

  const testRetrieval = async (event: React.FormEvent) => {
    event.preventDefault();
    const query = ragQuery.trim();
    if (query.length < 3 || !ragConfig) return;
    setIsTestingRag(true);
    setRagError(null);
    setRagResult(null);
    try {
      setRagResult(await api.testRagRetrieval({
        query,
        top_k: ragConfig.retrieval_top_k,
        hybrid: ragConfig.hybrid_search_enabled,
        reranking: ragConfig.reranking_enabled,
        min_similarity: ragConfig.min_similarity_score,
      }));
    } catch (error) {
      setRagError(`RAG retrieval test failed: ${errorText(error)}`);
    } finally {
      setIsTestingRag(false);
    }
  };

  const selectTab = (tab: SettingsTab) => {
    setActiveTab(tab);
    if (tab === 'ai-rag') void loadRagConfiguration();
  };

  const systemStatus = engineSummary?.status || 'Unknown';
  const allEngines = Object.entries(engineSummary?.engines ?? {});
  const connectedProviders = integrations?.integrations ?? [];
  const engineByKey = (key: string): EngineDetail | undefined => engineSummary?.engines[key];

  const renderEngineRow = ([key, engine]: [string, EngineDetail]) => (
    <div key={key} className="rounded-lg border p-4" style={{ ...surfaceStyle, borderColor: 'var(--border)' }}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="font-semibold">{engine.name}</div>
          {engine.description && <p className="mt-1 text-xs" style={detailStyle}>{engine.description}</p>}
        </div>
        <StatusBadge status={engine.state} />
      </div>
      <dl className="mt-4 grid grid-cols-1 gap-x-4 gap-y-3 text-xs sm:grid-cols-2">
        <div><dt style={detailStyle}>Provider</dt><dd className="mt-1 font-medium">{engine.provider || 'Not configured'}</dd></div>
        <div><dt style={detailStyle}>Model / version</dt><dd className="mt-1 font-mono">{engine.version || '—'}</dd></div>
        <div><dt style={detailStyle}>Connectivity</dt><dd className="mt-1">{engine.connected === null || engine.connected === undefined ? 'Not tested' : engine.connected ? 'Connected' : 'Not connected'}</dd></div>
        <div><dt style={detailStyle}>Last checked</dt><dd className="mt-1">{formatTime(engine.last_checked)}</dd></div>
        <div><dt style={detailStyle}>Last successful operation</dt><dd className="mt-1">{formatTime(engine.last_successful_operation)}</dd></div>
      </dl>
      {engine.details && <p className="mt-3 text-xs leading-relaxed" style={detailStyle}>{engine.details}</p>}
      {engine.error_message && (
        <div className="mt-3 rounded-md border border-rose-500/30 bg-rose-500/5 p-3 text-xs text-rose-600 dark:text-rose-300">
          {engine.error_category ? `${engine.error_category}: ` : ''}{engine.error_message}
        </div>
      )}
    </div>
  );

  return (
    <div className="mx-auto max-w-7xl space-y-5">
      <header className="flex flex-col gap-4 border-b pb-5 sm:flex-row sm:items-center sm:justify-between" style={{ borderColor: 'var(--border)' }}>
        <div>
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.16em]" style={{ color: 'var(--brand)' }}>
            <Settings2 className="h-4 w-4" /> Settings
          </div>
          <h1 className="mt-2 text-2xl font-bold tracking-tight">System configuration &amp; health</h1>
          <p className="mt-1 text-sm" style={detailStyle}>Inspect runtime services, providers, persisted settings, and recent diagnostics.</p>
        </div>
        <Button variant="primary" size="sm" onClick={() => void refreshHealth()} isLoading={isRefreshing}>
          <RefreshCw className="mr-1.5 h-4 w-4" /> Refresh System Health
        </Button>
      </header>

      {pageError && (
        <div role="alert" className="flex gap-2 rounded-lg border border-amber-500/30 bg-amber-500/5 p-3 text-sm text-amber-700 dark:text-amber-300">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" /> {pageError}
        </div>
      )}

      <nav aria-label="Settings sections" className="flex gap-1 overflow-x-auto border-b pb-1" style={{ borderColor: 'var(--border)' }}>
        {tabs.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            type="button"
            onClick={() => selectTab(id)}
            aria-current={activeTab === id ? 'page' : undefined}
            className="inline-flex shrink-0 items-center gap-2 rounded-t-md border-b-2 px-3 py-2.5 text-xs font-medium transition-colors"
            style={{
              color: activeTab === id ? 'var(--text-1)' : 'var(--text-3)',
              borderColor: activeTab === id ? 'var(--brand)' : 'transparent',
            }}
          >
            <Icon className="h-4 w-4" /> {label}
          </button>
        ))}
      </nav>

      {isLoading && !engineSummary ? (
        <div className="flex min-h-48 items-center justify-center gap-2 text-sm" style={detailStyle}>
          <LoaderCircle className="h-4 w-4 animate-spin" /> Loading system health…
        </div>
      ) : (
        <>
          {activeTab === 'overview' && (
            <div className="space-y-5">
              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
                <MetricCard label="Overall status" value={systemStatus} note={health?.status ? `API: ${health.status}` : 'Backend status unavailable'} icon={HeartPulse} tone={systemStatus === 'Operational' ? 'var(--positive)' : undefined} />
                <MetricCard label="Engines ready" value={`${engineSummary?.ready_count ?? 0} / ${engineSummary?.total_engines ?? 0}`} note="Ready or connected" icon={Cpu} />
                <MetricCard label="Degraded engines" value={engineSummary?.degraded_count ?? 0} note={`${engineSummary?.configured_count ?? 0} configured, not verified`} icon={AlertTriangle} tone="var(--warning)" />
                <MetricCard label="Unavailable services" value={engineSummary?.unavailable_count ?? 0} note={`${engineSummary?.disabled_count ?? 0} disabled`} icon={ShieldAlert} tone={(engineSummary?.unavailable_count ?? 0) > 0 ? 'var(--negative)' : undefined} />
                <MetricCard label="Last health check" value={engineSummary ? formatTime(engineSummary.timestamp) : 'Unknown'} note="From backend verification timestamp" icon={Clock3} />
              </div>
              <SectionCard title="System status" description="A concise view of the currently registered backend engines.">
                {engineSummary ? (
                  <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                    {allEngines.map(([key, engine]) => (
                      <div key={key} className="flex items-center justify-between gap-3 rounded-lg border p-3" style={{ ...surfaceStyle, borderColor: 'var(--border)' }}>
                        <div className="min-w-0">
                          <div className="truncate text-sm font-medium">{engine.name}</div>
                          <div className="mt-1 truncate text-xs" style={detailStyle}>{engine.provider || 'No provider configured'}</div>
                        </div>
                        <StatusBadge status={engine.state} />
                      </div>
                    ))}
                  </div>
                ) : <p className="text-sm" style={detailStyle}>Engine status is unavailable.</p>}
              </SectionCard>
              <SectionCard title="Runtime configuration" description="Safe, non-secret environment and service information reported by the backend.">
                {configuration ? (
                  <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                    <Info label="Application" value={configuration.app_name} note={`${configuration.environment} · ${configuration.data_mode} data mode`} />
                    <Info label="Primary AI provider" value={configuration.llm.primary_provider || 'None configured'} note={configuration.llm.primary_provider ? 'Credentials configured; connectivity status is shown in Integrations.' : 'Configure provider credentials in the backend environment.'} />
                    <Info label="Database" value={configuration.database.provider} note={configuration.database.reachable ? 'Reachable' : 'Not reachable'} />
                    <Info label="Embedding model" value={configuration.embedding.model} note={`${configuration.embedding.dimension} dimensions · ${configuration.embedding.device}`} />
                  </div>
                ) : <p className="text-sm" style={detailStyle}>Safe configuration details are unavailable.</p>}
              </SectionCard>
            </div>
          )}

          {activeTab === 'engines' && (
            <div className="space-y-4">
              <SectionCard title="Engine health registry" description="Configuration alone is not reported as operational. Unverified services remain labeled configured until tested.">
                {allEngines.length ? (
                  <div className="grid gap-3 lg:grid-cols-2">{allEngines.map(renderEngineRow)}</div>
                ) : <p className="text-sm" style={detailStyle}>No engine health records are available.</p>}
              </SectionCard>
            </div>
          )}

          {activeTab === 'ai-rag' && (
            <div className="space-y-5">
              <SectionCard title="AI provider configuration" description="Model identifiers come from backend environment configuration. Health status is based on actual provider probes, not initialization.">
                <div className="grid gap-3 lg:grid-cols-2">
                  {(['gemini', 'groq'] as const).map((providerKey) => {
                    const provider = configuration?.llm[providerKey];
                    const healthRecord = connectedProviders.find((item) =>
                      item.provider.toLowerCase().includes(providerKey === 'gemini' ? 'gemini' : 'groq'),
                    );
                    return (
                      <div key={providerKey} className="rounded-lg border p-4" style={{ ...surfaceStyle, borderColor: 'var(--border)' }}>
                        <div className="flex items-start justify-between gap-2">
                          <div>
                            <h3 className="font-semibold">{providerKey === 'gemini' ? 'Google Gemini' : 'Groq'}</h3>
                            <p className="mt-1 text-xs" style={detailStyle}>Configured model: <span className="font-mono">{provider?.model || 'Unavailable'}</span></p>
                            <p className="mt-1 text-xs" style={detailStyle}>Fallback model: <span className="font-mono">{provider?.fallback_model || 'Not configured'}</span></p>
                          </div>
                          <StatusBadge status={healthRecord?.status || (provider?.configured ? 'Configured' : 'Not configured')} />
                        </div>
                        <div className="mt-4 space-y-2 border-t pt-3 text-xs" style={{ borderColor: 'var(--border)' }}>
                          <p><span style={detailStyle}>Selected active model: </span><span className="font-mono">{healthRecord?.active_model || 'Not verified'}</span></p>
                          <p><span style={detailStyle}>Last successful test: </span>{formatTime(healthRecord?.last_successful_test)}</p>
                          {healthRecord?.error_message && <p className="text-rose-500">{healthRecord.error_category ? `${healthRecord.error_category}: ` : ''}{healthRecord.error_message}</p>}
                          {!healthRecord && <p style={detailStyle}>Run Refresh System Health to test configured provider connectivity.</p>}
                        </div>
                      </div>
                    );
                  })}
                </div>
                <p className="mt-4 text-xs" style={detailStyle}>API keys and secret values are never displayed here.</p>
              </SectionCard>

              <SectionCard title="RAG configuration" description="These controls are stored by the backend as a versioned RAG configuration.">
                {isLoadingRag && <div className="flex items-center gap-2 text-sm" style={detailStyle}><LoaderCircle className="h-4 w-4 animate-spin" /> Loading persisted configuration…</div>}
                {ragLoadError && <p role="alert" className="mb-3 text-sm text-rose-500">{ragLoadError}</p>}
                {ragSaved && <p role="status" className="mb-3 text-sm text-emerald-600">RAG configuration saved as {ragConfig?.config_version}.</p>}
                {ragConfig && (
                  <div className="space-y-5">
                    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                      <Info label="Embedding model" value={ragConfig.embedding_model} note={`${ragConfig.embedding_dimension} dimensions · ${ragConfig.embedding_device}`} />
                      <Info label="Active configuration" value={ragConfig.config_version} note="Persisted configuration version" />
                      <Info label="Chunk strategy" value={ragConfig.chunk_strategy} note={`${ragConfig.chunk_size} chunk size · ${ragConfig.chunk_overlap} overlap`} />
                    </div>
                    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                      <NumberField label="Chunk size" min={100} max={10000} value={ragConfig.chunk_size} onChange={(value) => setRagConfig({ ...ragConfig, chunk_size: value })} />
                      <NumberField label="Chunk overlap" min={0} max={5000} value={ragConfig.chunk_overlap} onChange={(value) => setRagConfig({ ...ragConfig, chunk_overlap: value })} />
                      <NumberField label="Retrieval top K" min={1} max={25} value={ragConfig.retrieval_top_k} onChange={(value) => setRagConfig({ ...ragConfig, retrieval_top_k: value })} />
                      <NumberField label="Minimum similarity" min={0} max={1} step={0.05} value={ragConfig.min_similarity_score} onChange={(value) => setRagConfig({ ...ragConfig, min_similarity_score: value })} />
                      <NumberField label="Vector weight" min={0} max={1} step={0.05} value={ragConfig.vector_weight} onChange={(value) => setRagConfig({ ...ragConfig, vector_weight: value })} />
                      <NumberField label="Keyword weight" min={0} max={1} step={0.05} value={ragConfig.keyword_weight} onChange={(value) => setRagConfig({ ...ragConfig, keyword_weight: value })} />
                      <label className="block text-xs font-medium">
                        LLM provider
                        <select value={ragConfig.llm_provider} onChange={(event) => setRagConfig({ ...ragConfig, llm_provider: event.target.value })} className="mt-1.5 w-full rounded-md border px-3 py-2" style={fieldStyle}>
                          <option value="gemini">Gemini</option><option value="groq">Groq</option>
                        </select>
                      </label>
                      <TextField label="RAG model identifier" value={ragConfig.llm_model} onChange={(value) => setRagConfig({ ...ragConfig, llm_model: value })} />
                      <NumberField label="LLM temperature" min={0} max={2} step={0.1} value={ragConfig.llm_temperature} onChange={(value) => setRagConfig({ ...ragConfig, llm_temperature: value })} />
                      <NumberField label="LLM max tokens" min={1} max={32768} value={ragConfig.llm_max_tokens} onChange={(value) => setRagConfig({ ...ragConfig, llm_max_tokens: value })} />
                      <NumberField label="Reranking top K" min={1} max={25} value={ragConfig.reranking_top_k} onChange={(value) => setRagConfig({ ...ragConfig, reranking_top_k: value })} />
                    </div>
                    <div className="flex flex-wrap gap-5 text-sm">
                      <Toggle label="Hybrid search" checked={ragConfig.hybrid_search_enabled} onChange={(checked) => setRagConfig({ ...ragConfig, hybrid_search_enabled: checked })} />
                      <Toggle label="Reranking" checked={ragConfig.reranking_enabled} onChange={(checked) => setRagConfig({ ...ragConfig, reranking_enabled: checked })} />
                      <Toggle label="Require citations" checked={ragConfig.require_citations} disabled onChange={() => undefined} />
                    </div>
                    <p className="text-xs" style={detailStyle}>Embedding model changes are not exposed here because the backend requires documents to be re-embedded after a model or dimension change.</p>
                    <Button variant="primary" size="sm" onClick={() => void saveRagConfiguration()} isLoading={isSavingRag}>
                      <Save className="mr-1.5 h-4 w-4" /> Save RAG Configuration
                    </Button>
                  </div>
                )}
              </SectionCard>

              <SectionCard title="Test retrieval" description="Runs the existing retrieval endpoint without generating an answer or consuming an LLM completion.">
                <form onSubmit={(event) => void testRetrieval(event)} className="flex flex-col gap-3 sm:flex-row">
                  <label className="sr-only" htmlFor="rag-query">Retrieval query</label>
                  <input id="rag-query" value={ragQuery} onChange={(event) => setRagQuery(event.target.value)} minLength={3} placeholder="Enter a query to test document retrieval" className="min-w-0 flex-1 rounded-md border px-3 py-2 text-sm" style={fieldStyle} />
                  <Button type="submit" variant="outline" size="sm" isLoading={isTestingRag} disabled={!ragConfig || ragQuery.trim().length < 3}>
                    <Search className="mr-1.5 h-4 w-4" /> Test Retrieval
                  </Button>
                </form>
                {ragError && <p role="alert" className="mt-3 text-sm text-rose-500">{ragError}</p>}
                {ragResult && (
                  <div className="mt-4 space-y-3">
                    <div className="flex flex-wrap gap-2 text-xs">
                      <Badge variant="neutral">Route: {ragResult.route}</Badge>
                      <Badge variant="neutral">{ragResult.retrieved_count} chunks</Badge>
                      <Badge variant="neutral">Query: {ragResult.rewritten_query}</Badge>
                    </div>
                    {ragResult.chunks.length ? ragResult.chunks.map((chunk) => (
                      <article key={chunk.chunk_id} className="rounded-md border p-3" style={{ ...surfaceStyle, borderColor: 'var(--border)' }}>
                        <div className="flex flex-wrap justify-between gap-2 text-xs">
                          <strong>{chunk.document_title || 'Untitled document'}</strong>
                          <span style={detailStyle}>{chunk.section || 'No section'}{chunk.page_number ? ` · page ${chunk.page_number}` : ''} · score {chunk.similarity_score.toFixed(3)}</span>
                        </div>
                        <p className="mt-2 whitespace-pre-wrap text-xs leading-relaxed" style={detailStyle}>{chunk.content}</p>
                      </article>
                    )) : <p className="text-sm" style={detailStyle}>The retrieval service returned no matching chunks.</p>}
                  </div>
                )}
              </SectionCard>
            </div>
          )}

          {activeTab === 'integrations' && (
            <SectionCard title="External API integrations" description="Unprobed providers remain configured or untested; an explicit health refresh tests connectivity.">
              {integrations ? (
                <div className="space-y-3">
                  {integrations.integrations.map((item: IntegrationHealth) => (
                    <div key={item.provider} className="grid gap-3 rounded-lg border p-4 md:grid-cols-[minmax(160px,1fr)_auto_minmax(180px,1fr)_minmax(200px,2fr)] md:items-center" style={{ ...surfaceStyle, borderColor: 'var(--border)' }}>
                      <div>
                        <div className="text-sm font-semibold">{item.provider}</div>
                        <div className="mt-1 text-xs" style={detailStyle}>{item.purpose || item.model || 'External service'}</div>
                      </div>
                      <StatusBadge status={item.status} />
                      <div className="text-xs">
                        <div className="font-mono">{item.configured_model || item.model || '—'}</div>
                        {item.active_model && <div className="mt-1" style={detailStyle}>Active: {item.active_model}</div>}
                      </div>
                      <div className="text-xs">
                        <div>{item.error_category ? `${item.error_category}: ` : ''}{item.error_message || item.information || (item.operational ? 'Operational' : 'No test result available.')}</div>
                        <div className="mt-1" style={detailStyle}>Last successful test: {formatTime(item.last_successful_test)}</div>
                      </div>
                    </div>
                  ))}
                  <p className="pt-1 text-xs" style={detailStyle}>Status counts: {integrations.connected_count} connected · {integrations.degraded_count} degraded · {integrations.failed_count} unavailable · {integrations.not_configured_count} not configured.</p>
                </div>
              ) : <p className="text-sm" style={detailStyle}>Integration status is unavailable.</p>}
            </SectionCard>
          )}

          {activeTab === 'database' && (
            <div className="space-y-5">
              <SectionCard title="Database and storage" description="Shows the configured backend and current connectivity; no credentials or connection strings are exposed.">
                {configuration ? (
                  <div className="grid gap-3 sm:grid-cols-2">
                    <ServiceCard title="Relational database" icon={Database} value={configuration.database.provider} status={configuration.database.reachable ? 'Connected' : 'Unavailable'} description={configuration.database.fallback ? 'The application is using its SQLite development fallback.' : 'Configured relational database; no fallback is reported.'} />
                    <ServiceCard title="Vector retrieval" icon={LayersIcon} value={engineByKey('vector_store')?.provider || 'pgvector'} status={engineByKey('vector_store')?.state || 'Unknown'} description={engineByKey('vector_store')?.details || 'Vector store status is not available.'} />
                    <ServiceCard title="MongoDB integration" icon={Server} value={configuration.mongodb.configured ? configuration.mongodb.database || 'MongoDB configured' : 'Not configured'} status={configuration.mongodb.connected ? 'Connected' : configuration.mongodb.configured ? 'Unavailable' : 'Not configured'} description="Separate document/chunk integration; active RAG retrieval uses the vector retrieval store shown above." />
                    <ServiceCard title="Document storage" icon={HardDrive} value={engineByKey('storage')?.provider || 'Unknown'} status={engineByKey('storage')?.state || 'Unknown'} description={engineByKey('storage')?.details || 'Storage health is not available.'} />
                  </div>
                ) : <p className="text-sm" style={detailStyle}>Database and storage details are unavailable.</p>}
              </SectionCard>
              <SectionCard title="Runtime environment" description="Public operational values reported by the backend.">
                {configuration ? (
                  <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                    <Info label="Environment" value={configuration.environment} note={configuration.app_name} />
                    <Info label="Data mode" value={configuration.data_mode} note="Controls live or demo integration behavior" />
                    <Info label="Upload storage" value={configuration.integrations.supabase_storage_configured ? 'Supabase Storage configured' : 'Local filesystem'} note={configuration.integrations.supabase_storage_configured ? 'Connectivity is not implied by configuration.' : 'Local storage path is not exposed.'} />
                    <Info label="Backend API" value={health?.status || 'Unknown'} note={`Version response timestamp: ${formatTime(health?.timestamp)}`} />
                  </div>
                ) : <p className="text-sm" style={detailStyle}>Runtime configuration is unavailable.</p>}
              </SectionCard>
            </div>
          )}

          {activeTab === 'preferences' && (
            <SectionCard title="Application preferences" description="Preferences are stored in this browser profile.">
              <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                <div className="flex items-start gap-3">
                  <span className="rounded-lg p-2" style={{ color: 'var(--brand)', background: 'var(--brand-muted)' }}>
                    {theme === 'dark' ? <Moon className="h-5 w-5" /> : <Sun className="h-5 w-5" />}
                  </span>
                  <div>
                    <div className="font-semibold">Color theme</div>
                    <p className="mt-1 text-xs" style={detailStyle}>Current theme: {theme}. Saved locally as your application preference.</p>
                  </div>
                </div>
                <Button variant="outline" size="sm" onClick={toggleTheme}>Switch to {theme === 'dark' ? 'light' : 'dark'} theme</Button>
              </div>
            </SectionCard>
          )}

          {activeTab === 'diagnostics' && (
            <SectionCard title="System logs & diagnostics" description="This view reports sanitized diagnostics from the latest health checks, not raw server log files.">
              {!diagnostics ? <p className="text-sm" style={detailStyle}>No diagnostic result is available. Refresh system health to run checks.</p> : (
                <>
                  <div className="mb-4 flex flex-wrap items-center gap-2">
                    <Badge variant={diagnostics.issues.length ? 'warning' : 'gain'}>{diagnostics.issues.length} reported issues</Badge>
                    <span className="text-xs" style={detailStyle}>Refresh system health to update this list.</span>
                  </div>
                  {diagnostics.issues.length ? (
                    <div className="space-y-2">
                      {diagnostics.issues.map((issue, index) => (
                        <div key={`${issue.component}-${issue.category || ''}-${index}`} className="rounded-md border p-3" style={{ ...surfaceStyle, borderColor: 'var(--border)' }}>
                          <div className="flex flex-wrap items-center justify-between gap-2">
                            <div className="flex items-center gap-2 text-sm font-semibold">
                              {issue.severity === 'error' ? <XCircle className="h-4 w-4 text-rose-500" /> : <AlertTriangle className="h-4 w-4 text-amber-500" />}
                              {issue.component}
                              {issue.category && <span className="font-normal" style={detailStyle}>· {issue.category}</span>}
                            </div>
                            <time className="text-xs" style={detailStyle}>{formatTime(issue.timestamp)}</time>
                          </div>
                          <p className="mt-2 text-xs leading-relaxed" style={detailStyle}>{issue.message}</p>
                        </div>
                      ))}
                    </div>
                  ) : <div className="rounded-lg border p-5 text-center text-sm" style={{ ...surfaceStyle, borderColor: 'var(--border)', color: 'var(--positive)' }}>No issues reported by the latest health checks.</div>}
                </>
              )}
            </SectionCard>
          )}
        </>
      )}
    </div>
  );
};

function Info({ label, value, note }: { label: string; value: string; note: string }) {
  return (
    <div className="min-w-0">
      <div className="text-xs" style={detailStyle}>{label}</div>
      <div className="mt-1 break-words text-sm font-semibold">{value}</div>
      <div className="mt-1 text-xs" style={detailStyle}>{note}</div>
    </div>
  );
}

function NumberField({
  label,
  min,
  max,
  step = 1,
  value,
  onChange,
}: {
  label: string;
  min: number;
  max: number;
  step?: number;
  value: number;
  onChange: (value: number) => void;
}) {
  return (
    <label className="block text-xs font-medium">
      {label}
      <input type="number" min={min} max={max} step={step} value={value} onChange={(event) => onChange(Number(event.target.value))} className="mt-1.5 w-full rounded-md border px-3 py-2" style={fieldStyle} />
    </label>
  );
}

function TextField({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return (
    <label className="block text-xs font-medium">
      {label}
      <input type="text" value={value} onChange={(event) => onChange(event.target.value)} className="mt-1.5 w-full rounded-md border px-3 py-2" style={fieldStyle} />
    </label>
  );
}

function Toggle({
  label,
  checked,
  disabled = false,
  onChange,
}: {
  label: string;
  checked: boolean;
  disabled?: boolean;
  onChange: (value: boolean) => void;
}) {
  return (
    <label className={`inline-flex items-center gap-2 text-xs ${disabled ? 'opacity-60' : 'cursor-pointer'}`}>
      <input type="checkbox" checked={checked} disabled={disabled} onChange={(event) => onChange(event.target.checked)} />
      {label}
    </label>
  );
}

function ServiceCard({
  title,
  value,
  status,
  description,
  icon: Icon,
}: {
  title: string;
  value: string;
  status: string;
  description: string;
  icon: React.ElementType;
}) {
  return (
    <div className="rounded-lg border p-4" style={{ ...surfaceStyle, borderColor: 'var(--border)' }}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2 text-sm font-semibold"><Icon className="h-4 w-4" style={{ color: 'var(--brand)' }} />{title}</div>
        <StatusBadge status={status} />
      </div>
      <div className="mt-3 text-sm font-medium">{value}</div>
      <p className="mt-1 text-xs leading-relaxed" style={detailStyle}>{description}</p>
    </div>
  );
}

const LayersIcon = FileStack;
