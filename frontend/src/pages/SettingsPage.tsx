import React, { useState, useEffect } from 'react';
import {
  Activity,
  Database,
  Cpu,
  Bot,
  Layers,
  Server,
  RefreshCw,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  HelpCircle,
  ShieldCheck,
} from 'lucide-react';
import { Card, CardHeader, CardTitle, CardContent } from '../components/ui/Card';
import { Badge } from '../components/ui/Badge';
import { Button } from '../components/ui/Button';
import { Logo } from '../components/brand/Logo';
import { useThemeStore } from '../stores/themeStore';
import { api } from '../services/api';
import { EnginesSummary } from '../types';

export const SettingsPage: React.FC = () => {
  const { theme, toggleTheme } = useThemeStore();
  const [engineSummary, setEngineSummary] = useState<EnginesSummary | null>(null);
  const [healthData, setHealthData] = useState<any>(null);
  const [integrationsData, setIntegrationsData] = useState<any>(null);
  const [isLoading, setIsLoading] = useState(false);

  const fetchStatus = async () => {
    setIsLoading(true);
    try {
      const [engines, health, integrations] = await Promise.all([
        api.getEngines(),
        api.getHealth(),
        api.getIntegrations().catch(() => null),
      ]);
      setEngineSummary(engines);
      setHealthData(health);
      setIntegrationsData(integrations);
    } catch (e) {
      console.error('Failed to load engines status:', e);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchStatus();
  }, []);

  const getStateBadge = (state: string) => {
    switch (state) {
      case 'Ready':
        return (
          <Badge variant="gain" size="sm">
            <CheckCircle2 className="w-3.5 h-3.5 mr-1" /> Ready
          </Badge>
        );
      case 'Degraded':
        return (
          <Badge variant="warning" size="sm">
            <AlertTriangle className="w-3.5 h-3.5 mr-1" /> Degraded
          </Badge>
        );
      case 'Disabled':
        return (
          <Badge variant="neutral" size="sm">
            <HelpCircle className="w-3.5 h-3.5 mr-1" /> Disabled
          </Badge>
        );
      case 'Failed':
        return (
          <Badge variant="loss" size="sm">
            <XCircle className="w-3.5 h-3.5 mr-1" /> Failed
          </Badge>
        );
      default:
        return <Badge size="sm">{state}</Badge>;
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-slate-200 dark:border-slate-800 pb-4">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
            Central Engine Registry & System Status
          </h1>
          <p className="text-xs sm:text-sm text-slate-500 dark:text-slate-400 mt-1">
            Real-time introspection and health monitoring across all backend engines & provider adapters
          </p>
        </div>
        <Button variant="primary" size="sm" onClick={fetchStatus} isLoading={isLoading}>
          <RefreshCw className="w-3.5 h-3.5 mr-1.5" /> Refresh Engines
        </Button>
      </div>

      {/* Engine Registry Metrics */}
      {engineSummary && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 font-tabular">
          <Card className="p-4">
            <span className="text-xs text-slate-400 font-mono block">Overall Status</span>
            <span
              className={`text-xl font-bold ${
                engineSummary.status === 'Healthy'
                  ? 'text-emerald-500'
                  : engineSummary.status === 'Degraded'
                  ? 'text-amber-500'
                  : 'text-rose-500'
              }`}
            >
              {engineSummary.status}
            </span>
          </Card>
          <Card className="p-4">
            <span className="text-xs text-slate-400 font-mono block">Engines Ready</span>
            <span className="text-xl font-bold text-emerald-500">
              {engineSummary.ready_count} / {engineSummary.total_engines}
            </span>
          </Card>
          <Card className="p-4">
            <span className="text-xs text-slate-400 font-mono block">Degraded / Demo</span>
            <span className="text-xl font-bold text-amber-500">{engineSummary.degraded_count}</span>
          </Card>
          <Card className="p-4">
            <span className="text-xs text-slate-400 font-mono block">Disabled Providers</span>
            <span className="text-xl font-bold text-slate-400">{engineSummary.disabled_count}</span>
          </Card>
        </div>
      )}

      {/* Central Engine Status Grid */}
      <Card>
        <CardHeader>
          <CardTitle>Engine Architecture & Provider Registry</CardTitle>
        </CardHeader>
        <CardContent className="p-0 overflow-x-auto">
          {engineSummary ? (
            <table className="w-full text-left text-xs font-tabular">
              <thead className="bg-slate-50 dark:bg-slate-900 text-slate-500 border-b border-slate-200 dark:border-slate-800 font-mono">
                <tr>
                  <th className="p-4">Engine Name</th>
                  <th className="p-4">Status</th>
                  <th className="p-4">Active Provider</th>
                  <th className="p-4">Engine Details / Connectivity</th>
                  <th className="p-4 text-right">Last Verified</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                {Object.entries(engineSummary.engines).map(([key, engine]) => (
                  <tr key={key} className="hover:bg-slate-50/80 dark:hover:bg-slate-850/50">
                    <td className="p-4 font-semibold text-slate-900 dark:text-slate-100 font-sans">
                      {engine.name}
                    </td>
                    <td className="p-4">{getStateBadge(engine.state)}</td>
                    <td className="p-4 font-mono text-cyan-500 font-medium">
                      {engine.provider || 'Core Engine'}
                    </td>
                    <td className="p-4 text-slate-600 dark:text-slate-300 font-sans max-w-md">
                      {engine.details}
                    </td>
                    <td className="p-4 text-right text-slate-400 font-mono text-[11px]">
                      {new Date(engine.last_checked).toLocaleTimeString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="py-12 text-center text-xs text-slate-400">Loading engine registry...</div>
          )}
        </CardContent>
      </Card>

      {/* External API Integration Audit Dashboard */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <div>
            <CardTitle>External API Integrations & Connectivity Audit</CardTitle>
            <p className="text-xs text-slate-500 mt-1">
              Live status, response latency, and endpoint availability for all third-party services.
            </p>
          </div>
          {integrationsData && (
            <div className="flex items-center gap-2">
              <Badge variant="gain" size="sm">
                {integrationsData.connected_count} Connected
              </Badge>
              {integrationsData.degraded_count > 0 && (
                <Badge variant="warning" size="sm">
                  {integrationsData.degraded_count} Degraded / Tier Limit
                </Badge>
              )}
            </div>
          )}
        </CardHeader>
        <CardContent className="p-0 overflow-x-auto">
          {integrationsData ? (
            <table className="w-full text-left text-xs font-tabular">
              <thead className="bg-slate-50 dark:bg-slate-900 text-slate-500 border-b border-slate-200 dark:border-slate-800 font-mono">
                <tr>
                  <th className="p-4">Provider</th>
                  <th className="p-4">Status</th>
                  <th className="p-4">Model / Endpoint</th>
                  <th className="p-4">Latency</th>
                  <th className="p-4">HTTP</th>
                  <th className="p-4">Operational Information</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                {integrationsData.integrations.map((item: any, idx: number) => (
                  <tr key={idx} className="hover:bg-slate-50/80 dark:hover:bg-slate-850/50">
                    <td className="p-4 font-semibold text-slate-900 dark:text-slate-100 font-sans">
                      {item.provider}
                    </td>
                    <td className="p-4">
                      {item.status === 'Connected' ? (
                        <Badge variant="gain" size="sm">
                          <CheckCircle2 className="w-3.5 h-3.5 mr-1" /> Connected
                        </Badge>
                      ) : item.status === 'Degraded' ? (
                        <Badge variant="warning" size="sm">
                          <AlertTriangle className="w-3.5 h-3.5 mr-1" /> Degraded
                        </Badge>
                      ) : item.status === 'Failed' ? (
                        <Badge variant="loss" size="sm">
                          <XCircle className="w-3.5 h-3.5 mr-1" /> Failed
                        </Badge>
                      ) : (
                        <Badge variant="neutral" size="sm">
                          <HelpCircle className="w-3.5 h-3.5 mr-1" /> Not Configured
                        </Badge>
                      )}
                    </td>
                    <td className="p-4 font-mono text-cyan-500 text-[11px]">
                      {item.model || '—'}
                    </td>
                    <td className="p-4 font-mono text-slate-700 dark:text-slate-300">
                      {item.latency_ms > 0 ? `${item.latency_ms} ms` : '—'}
                    </td>
                    <td className="p-4 font-mono">
                      {item.http_status ? (
                        <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                          item.http_status === 200 || item.http_status === 207
                            ? 'bg-emerald-500/10 text-emerald-500'
                            : 'bg-amber-500/10 text-amber-500'
                        }`}>
                          {item.http_status}
                        </span>
                      ) : (
                        '—'
                      )}
                    </td>
                    <td className="p-4 text-slate-600 dark:text-slate-300 font-sans max-w-md">
                      {item.information}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="py-8 text-center text-xs text-slate-400">Loading integrations audit...</div>
          )}
        </CardContent>
      </Card>

      {/* Brand Identity & Visual Assets */}
      <Card className="p-6 space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-200 dark:border-slate-800 pb-4">
          <div>
            <CardTitle>AlphaNexus Brand Identity &amp; Assets</CardTitle>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
              Official vector-extracted visual identity system with high-DPI raster and SVG assets.
            </p>
          </div>
          <Badge variant="gain" size="sm">Official Assets Active</Badge>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
          {/* Variant 1: Horizontal Dark */}
          <div className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900/50 flex flex-col justify-between space-y-3">
            <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Horizontal (Dark Mode)</div>
            <div className="py-4 px-3 flex items-center justify-center min-h-[70px] bg-[#070b16] rounded-lg border border-slate-800">
              <Logo variant="horizontal" theme="dark" height={28} />
            </div>
            <div className="text-[10px] font-mono text-slate-400">/brand/alphanexus-logo-dark.png</div>
          </div>

          {/* Variant 2: Horizontal Light */}
          <div className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900/50 flex flex-col justify-between space-y-3">
            <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Horizontal (Light Mode)</div>
            <div className="py-4 px-3 flex items-center justify-center min-h-[70px] bg-white rounded-lg border border-slate-200 shadow-sm">
              <Logo variant="horizontal" theme="light" height={28} />
            </div>
            <div className="text-[10px] font-mono text-slate-400">/brand/alphanexus-logo-light.png</div>
          </div>

          {/* Variant 2: Standalone Icon */}
          <div className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900/50 flex flex-col justify-between space-y-3">
            <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Standalone Symbol</div>
            <div className="py-4 flex items-center justify-center min-h-[70px]">
              <Logo variant="icon" height={38} />
            </div>
            <div className="text-[10px] font-mono text-slate-400">/brand/alphanexus-icon.png</div>
          </div>

          {/* Variant 3: Squircle App Icon */}
          <div className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900/50 flex flex-col justify-between space-y-3">
            <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider">App Squircle (PWA / iOS)</div>
            <div className="py-4 flex items-center justify-center min-h-[70px]">
              <Logo variant="squircle" height={42} />
            </div>
            <div className="text-[10px] font-mono text-slate-400">/brand/apple-touch-icon.png</div>
          </div>

          {/* Variant 5: Stacked / Compact */}
          <div className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900/50 flex flex-col justify-between space-y-3">
            <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Compact Stacked</div>
            <div className="py-3 px-2 flex items-center justify-center min-h-[70px] bg-white rounded-lg border border-slate-200 shadow-sm">
              <Logo variant="stacked" height={52} />
            </div>
            <div className="text-[10px] font-mono text-slate-400">/brand/alphanexus-logo-stacked.png</div>
          </div>
        </div>

        {/* Color Palette Tokens */}
        <div className="pt-2">
          <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">Brand Color System</div>
          <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 text-xs">
            <div className="p-2.5 rounded-lg border border-slate-200 dark:border-slate-800 flex items-center gap-2.5">
              <div className="w-5 h-5 rounded-md shrink-0 shadow-sm" style={{ background: '#00E5C9' }} />
              <div>
                <div className="font-semibold text-slate-800 dark:text-slate-200">Apex Cyan</div>
                <div className="font-mono text-[10px] text-slate-400">#00E5C9</div>
              </div>
            </div>
            <div className="p-2.5 rounded-lg border border-slate-200 dark:border-slate-800 flex items-center gap-2.5">
              <div className="w-5 h-5 rounded-md shrink-0 shadow-sm" style={{ background: '#2563EB' }} />
              <div>
                <div className="font-semibold text-slate-800 dark:text-slate-200">Cobalt Blue</div>
                <div className="font-mono text-[10px] text-slate-400">#2563EB</div>
              </div>
            </div>
            <div className="p-2.5 rounded-lg border border-slate-200 dark:border-slate-800 flex items-center gap-2.5">
              <div className="w-5 h-5 rounded-md shrink-0 shadow-sm" style={{ background: '#6366F1' }} />
              <div>
                <div className="font-semibold text-slate-800 dark:text-slate-200">Base Violet</div>
                <div className="font-mono text-[10px] text-slate-400">#6366F1</div>
              </div>
            </div>
            <div className="p-2.5 rounded-lg border border-slate-200 dark:border-slate-800 flex items-center gap-2.5">
              <div className="w-5 h-5 rounded-md shrink-0 shadow-sm" style={{ background: '#0E192D' }} />
              <div>
                <div className="font-semibold text-slate-800 dark:text-slate-200">Navy Text</div>
                <div className="font-mono text-[10px] text-slate-400">#0E192D</div>
              </div>
            </div>
            <div className="p-2.5 rounded-lg border border-slate-200 dark:border-slate-800 flex items-center gap-2.5">
              <div className="w-5 h-5 rounded-md shrink-0 shadow-sm bg-slate-900 border border-slate-700" style={{ background: '#FFFFFF' }} />
              <div>
                <div className="font-semibold text-slate-800 dark:text-slate-200">Dark Text</div>
                <div className="font-mono text-[10px] text-slate-400">#FFFFFF</div>
              </div>
            </div>
          </div>
        </div>
      </Card>

      {/* Configuration & Preferences */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <Card className="p-5 space-y-4">
          <CardTitle>Interface & Terminal Appearance</CardTitle>
          <div className="flex items-center justify-between pt-2">
            <div>
              <span className="text-sm font-semibold text-slate-900 dark:text-slate-100 block">
                Color Theme
              </span>
              <span className="text-xs text-slate-400">
                Currently using {theme === 'dark' ? 'Dark Terminal (Default)' : 'Light Fintech'}
              </span>
            </div>
            <Button variant="outline" size="sm" onClick={toggleTheme}>
              Toggle to {theme === 'dark' ? 'Light' : 'Dark'}
            </Button>
          </div>
        </Card>

        <Card className="p-5 space-y-4">
          <CardTitle>Environment & Deployment</CardTitle>
          <div className="space-y-2 text-xs font-mono text-slate-600 dark:text-slate-300">
            <div className="flex justify-between">
              <span>Environment:</span>
              <span className="font-bold text-cyan-500">{healthData?.environment || 'development'}</span>
            </div>
            <div className="flex justify-between">
              <span>Data Mode:</span>
              <span className="font-bold text-emerald-500">{healthData?.data_mode || 'demo'}</span>
            </div>
            <div className="flex justify-between">
              <span>Target Market:</span>
              <span className="font-bold text-slate-100">National Stock Exchange (NSE) + BSE</span>
            </div>
          </div>
        </Card>
      </div>
    </div>
  );
};

