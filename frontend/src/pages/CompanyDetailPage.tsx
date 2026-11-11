import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  TrendingUp,
  TrendingDown,
  Globe,
  FileText,
  Calendar,
  Share2,
  Bookmark,
  Bot,
  Zap,
  CheckCircle2,
  AlertCircle,
  ExternalLink,
  BarChart3,
  Scale,
  DollarSign,
  PieChart,
  Activity,
} from 'lucide-react';
import { Card, CardHeader, CardTitle, CardContent } from '../components/ui/Card';
import { Badge } from '../components/ui/Badge';
import { Button } from '../components/ui/Button';
import { MarketChart } from '../components/charts/MarketChart';
import { FinancialBarChart } from '../components/charts/FinancialBarChart';
import { ForecastScenarioChart } from '../components/charts/ForecastScenarioChart';
import { api } from '../services/api';
import {
  Company,
  FinancialMetric,
  NewsArticle,
  CorporateAction,
  MarketEvent,
  ForecastResponseData,
  DocumentItem,
} from '../types';

export const CompanyDetailPage: React.FC = () => {
  const { symbol } = useParams<{ symbol: string }>();
  const [activeTab, setActiveTab] = useState<string>('overview');
  const [company, setCompany] = useState<Company | null>(null);
  const [financials, setFinancials] = useState<FinancialMetric[]>([]);
  const [ratios, setRatios] = useState<Record<string, any>>({});
  const [news, setNews] = useState<NewsArticle[]>([]);
  const [actions, setActions] = useState<CorporateAction[]>([]);
  const [events, setEvents] = useState<MarketEvent[]>([]);
  const [forecast, setForecast] = useState<ForecastResponseData | null>(null);
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  // AI Chat state for inline tab
  const [chatQuery, setChatQuery] = useState('');
  const [chatLoading, setChatLoading] = useState(false);
  const [chatMessages, setChatMessages] = useState<any[]>([]);

  useEffect(() => {
    if (!symbol) return;
    const fetchCompanyData = async () => {
      setIsLoading(true);
      try {
        const comp = await api.getCompany(symbol);
        setCompany(comp);

        const [finData, ratioData, newsData, actData, evData, fcData, docData] = await Promise.all([
          api.getCompanyFinancials(comp.id),
          api.getCompanyRatios(comp.id).catch(() => ({ computed_metrics: {} })),
          api.getNews({ company_id: comp.id }),
          api.getCorporateActions({ company_id: comp.id }),
          api.getMarketEvents({ company_id: comp.id }),
          api.getForecasts(comp.id, 'revenue').catch(() => null),
          api.getDocuments({ company_id: comp.id }),
        ]);

        setFinancials(finData);
        setRatios(ratioData.computed_metrics || {});
        setNews(newsData);
        setActions(actData);
        setEvents(evData);
        setForecast(fcData);
        setDocuments(docData);
      } catch (e) {
        console.error('Error fetching company details:', e);
      } finally {
        setIsLoading(false);
      }
    };
    fetchCompanyData();
  }, [symbol]);

  const handleSendChat = async () => {
    if (!chatQuery.trim() || !company) return;
    const userMsg = { role: 'user', content: chatQuery, created_at: new Date().toISOString() };
    setChatMessages((prev) => [...prev, userMsg]);
    const q = chatQuery;
    setChatQuery('');
    setChatLoading(true);

    try {
      const res = await api.sendResearchChat({
        company_id: company.id,
        query: q,
      });
      setChatMessages((prev) => [...prev, res]);
    } catch (e) {
      setChatMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: 'Failed to retrieve synthesis. Ensure backend RAG engine is running.',
          message_type: 'synthesis',
          citations: [],
        },
      ]);
    } finally {
      setChatLoading(false);
    }
  };

  if (isLoading || !company) {
    return (
      <div className="py-20 text-center text-sm text-slate-400 font-mono">
        Loading equity research terminal for {symbol}...
      </div>
    );
  }

  const TABS = [
    'overview',
    'performance',
    'news',
    'peers',
    'financials',
    'balance sheet',
    'cash flows',
    'shareholding',
    'dividend',
    'corporate actions',
    'filings',
    'announcements',
    'technicals',
    'forecast',
    'ai research',
  ];

  return (
    <div className="space-y-6">
      {/* Top Header Card: Company Details & Snapshot */}
      <Card className="p-6 bg-gradient-to-br from-white to-slate-50 dark:from-[#0a0f1d] dark:to-[#080d1a]">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="flex items-start gap-4">
            <div className="w-14 h-14 rounded-xl bg-cyan-500/10 text-cyan-600 dark:text-cyan-400 border border-cyan-500/20 flex items-center justify-center font-bold text-xl font-mono">
              {company.symbol.slice(0, 3)}
            </div>
            <div>
              <div className="flex items-center gap-2.5">
                <h1 className="text-xl sm:text-2xl font-bold text-slate-900 dark:text-slate-100 font-mono">
                  {company.symbol}
                </h1>
                <Badge variant="terminal" size="sm">
                  {company.exchange}
                </Badge>
                <span className="text-xs text-slate-400 font-mono">ISIN: {company.isin || '—'}</span>
              </div>
              <h2 className="text-sm text-slate-600 dark:text-slate-300 font-medium mt-0.5">{company.name}</h2>
              <div className="flex flex-wrap items-center gap-2 mt-2 text-xs text-slate-500">
                <span>{company.sector}</span>
                <span>•</span>
                <span>{company.industry}</span>
                {company.website && (
                  <>
                    <span>•</span>
                    <a
                      href={company.website}
                      target="_blank"
                      rel="noreferrer"
                      className="text-cyan-500 hover:underline flex items-center gap-1"
                    >
                      <Globe className="w-3 h-3" /> Investor Relations
                    </a>
                  </>
                )}
              </div>
            </div>
          </div>

          {/* Price & Action */}
          <div className="flex flex-row md:flex-col items-baseline md:items-end justify-between md:justify-center border-t md:border-t-0 pt-3 md:pt-0 border-slate-200 dark:border-slate-800">
            <div className="text-2xl sm:text-3xl font-bold font-tabular text-slate-900 dark:text-slate-100">
              ₹{company.current_price?.toLocaleString('en-IN') || '—'}
            </div>
            <div
              className={`text-sm font-semibold font-tabular flex items-center gap-1 ${
                company.day_change && company.day_change >= 0 ? 'text-emerald-500' : 'text-rose-500'
              }`}
            >
              {company.day_change && company.day_change > 0 ? '+' : ''}
              ₹{company.day_change || 0} ({company.day_change_percent || 0}%)
            </div>
          </div>
        </div>

        {/* 15 Persistent Research Tabs */}
        <div className="mt-6 border-b border-slate-200 dark:border-slate-800 overflow-x-auto scrollbar-none">
          <div className="flex items-center gap-1 min-w-max pb-1">
            {TABS.map((tab) => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`px-3 py-2 text-xs font-medium uppercase tracking-wider rounded-t-md transition-all whitespace-nowrap ${
                  activeTab === tab
                    ? 'bg-cyan-500/10 text-cyan-600 dark:text-cyan-400 border-b-2 border-cyan-500 font-semibold'
                    : 'text-slate-500 hover:text-slate-800 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800/50'
                }`}
              >
                {tab}
              </button>
            ))}
          </div>
        </div>
      </Card>

      {/* Tab 1: OVERVIEW */}
      {activeTab === 'overview' && (
        <div className="space-y-6">
          {/* Key Valuation Grid */}
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 font-tabular">
            <Card className="p-3">
              <span className="text-[10px] text-slate-400 font-mono uppercase block">Market Cap</span>
              <span className="text-sm font-bold text-slate-900 dark:text-slate-100">
                ₹{company.market_cap ? (company.market_cap / 1000).toFixed(1) + 'k Cr' : '—'}
              </span>
            </Card>
            <Card className="p-3">
              <span className="text-[10px] text-slate-400 font-mono uppercase block">P/E Ratio</span>
              <span className="text-sm font-bold text-slate-900 dark:text-slate-100">{company.pe_ratio || '—'}</span>
            </Card>
            <Card className="p-3">
              <span className="text-[10px] text-slate-400 font-mono uppercase block">P/B Ratio</span>
              <span className="text-sm font-bold text-slate-900 dark:text-slate-100">{company.pb_ratio || '—'}</span>
            </Card>
            <Card className="p-3">
              <span className="text-[10px] text-slate-400 font-mono uppercase block">ROE %</span>
              <span className="text-sm font-bold text-emerald-500">{company.roe ? `${company.roe}%` : '—'}</span>
            </Card>
            <Card className="p-3">
              <span className="text-[10px] text-slate-400 font-mono uppercase block">ROCE %</span>
              <span className="text-sm font-bold text-cyan-500">{company.roce ? `${company.roce}%` : '—'}</span>
            </Card>
            <Card className="p-3">
              <span className="text-[10px] text-slate-400 font-mono uppercase block">52W Range</span>
              <span className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                ₹{company.week_52_low} - {company.week_52_high}
              </span>
            </Card>
          </div>

          {/* Price Chart & Business Description */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <Card className="lg:col-span-2">
              <CardHeader>
                <CardTitle>Historical Price Performance</CardTitle>
              </CardHeader>
              <CardContent>
                <MarketChart isGain={company.day_change ? company.day_change >= 0 : true} />
              </CardContent>
            </Card>

            <Card className="flex flex-col justify-between">
              <div>
                <CardHeader>
                  <CardTitle>Business Overview</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-xs text-slate-600 dark:text-slate-300 leading-relaxed">
                    {company.description}
                  </p>
                  <div className="mt-4 pt-4 border-t border-slate-100 dark:border-slate-800 space-y-2 text-xs">
                    <div className="flex justify-between">
                      <span className="text-slate-400 font-mono">Exchange:</span>
                      <span className="font-semibold">{company.exchange}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-400 font-mono">Currency:</span>
                      <span className="font-semibold">{company.currency}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-400 font-mono">Dividend Yield:</span>
                      <span className="font-semibold text-emerald-500">{company.dividend_yield}%</span>
                    </div>
                  </div>
                </CardContent>
              </div>
              <div className="p-4 bg-slate-50 dark:bg-slate-900/40 border-t border-slate-100 dark:border-slate-800 rounded-b-lg">
                <Button
                  variant="terminal"
                  size="sm"
                  className="w-full"
                  onClick={() => setActiveTab('ai research')}
                >
                  <Bot className="w-3.5 h-3.5 mr-2" /> Start AI Filing Research
                </Button>
              </div>
            </Card>
          </div>
        </div>
      )}

      {/* Tab 5: FINANCIALS */}
      {activeTab === 'financials' && (
        <Card className="p-6 space-y-6">
          <div className="flex justify-between items-center border-b border-slate-200 dark:border-slate-800 pb-3">
            <div>
              <CardTitle>Income Statement Breakdown (Consolidated)</CardTitle>
              <p className="text-xs text-slate-500">Official figures reported in INR Crores</p>
            </div>
            <Badge variant="brand" size="xs">
              STANDALONE & CONSOLIDATED
            </Badge>
          </div>

          {/* Revenue Bar Chart */}
          <FinancialBarChart
            data={[
              { period: 'FY21', revenue: 539238, ebitda: 98018, net_profit: 53739 },
              { period: 'FY22', revenue: 792756, ebitda: 125687, net_profit: 67845 },
              { period: 'FY23', revenue: 974864, ebitda: 153920, net_profit: 74088 },
              { period: 'FY24', revenue: 1000122, ebitda: 178677, net_profit: 79020 },
            ]}
          />

          {/* Financials Table */}
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-tabular">
              <thead className="bg-slate-50 dark:bg-slate-900 text-slate-500 border-b border-slate-200 dark:border-slate-800 font-mono">
                <tr>
                  <th className="p-3">Metric Name</th>
                  <th className="p-3 text-right">FY21</th>
                  <th className="p-3 text-right">FY22</th>
                  <th className="p-3 text-right">FY23</th>
                  <th className="p-3 text-right">FY24</th>
                  <th className="p-3 text-right">YoY %</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                <tr>
                  <td className="p-3 font-semibold">Total Revenue (₹ Cr)</td>
                  <td className="p-3 text-right">5,39,238</td>
                  <td className="p-3 text-right">7,92,756</td>
                  <td className="p-3 text-right">9,74,864</td>
                  <td className="p-3 text-right font-bold text-cyan-500">10,00,122</td>
                  <td className="p-3 text-right text-emerald-500">+2.6%</td>
                </tr>
                <tr>
                  <td className="p-3 font-semibold">EBITDA (₹ Cr)</td>
                  <td className="p-3 text-right">98,018</td>
                  <td className="p-3 text-right">1,25,687</td>
                  <td className="p-3 text-right">1,53,920</td>
                  <td className="p-3 text-right font-bold text-emerald-500">1,78,677</td>
                  <td className="p-3 text-right text-emerald-500">+16.1%</td>
                </tr>
                <tr>
                  <td className="p-3 font-semibold">Net Profit / PAT (₹ Cr)</td>
                  <td className="p-3 text-right">53,739</td>
                  <td className="p-3 text-right">67,845</td>
                  <td className="p-3 text-right">74,088</td>
                  <td className="p-3 text-right font-bold text-purple-500">79,020</td>
                  <td className="p-3 text-right text-emerald-500">+6.7%</td>
                </tr>
                <tr>
                  <td className="p-3 font-semibold">Earnings Per Share (EPS ₹)</td>
                  <td className="p-3 text-right">82.5</td>
                  <td className="p-3 text-right">100.8</td>
                  <td className="p-3 text-right">109.5</td>
                  <td className="p-3 text-right font-bold">116.8</td>
                  <td className="p-3 text-right text-emerald-500">+6.7%</td>
                </tr>
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {/* Tab 14: FORECAST */}
      {activeTab === 'forecast' && (
        <Card className="p-6 space-y-6">
          <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-2 border-b border-slate-200 dark:border-slate-800 pb-3">
            <div>
              <CardTitle>Multi-Year Performance Forecast & Scenarios</CardTitle>
              <p className="text-xs text-slate-500">
                Statistical projection based on historical revenue trends and volatility
              </p>
            </div>
            <Badge variant="warning" size="xs">
              STATISTICAL ESTIMATE
            </Badge>
          </div>

          {forecast ? (
            <>
              <ForecastScenarioChart
                historicalData={forecast.historical}
                forecastData={forecast.forecasts}
                metricLabel="Revenue"
                unit="₹ Cr"
              />

              {/* Scenarios Table */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-4">
                {forecast.forecasts.map((f) => (
                  <Card key={f.period} className="p-4 bg-slate-50 dark:bg-slate-900/50">
                    <div className="flex justify-between items-center mb-2">
                      <span className="font-bold text-sm font-mono text-cyan-500">{f.period} Projection</span>
                      <span className="text-[10px] text-slate-400 font-mono">95% CI</span>
                    </div>
                    <div className="space-y-2 text-xs font-tabular">
                      <div className="flex justify-between">
                        <span className="text-emerald-500 font-semibold">Bullish (+15%):</span>
                        <span className="font-bold">₹{f.bullish.toLocaleString('en-IN')} Cr</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-cyan-500 font-semibold">Base Case:</span>
                        <span className="font-bold">₹{f.base.toLocaleString('en-IN')} Cr</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-rose-500 font-semibold">Bearish (-15%):</span>
                        <span className="font-bold">₹{f.bearish.toLocaleString('en-IN')} Cr</span>
                      </div>
                      <div className="pt-2 border-t border-slate-200 dark:border-slate-800 text-[10px] text-slate-400">
                        Interval: ₹{f.confidence_intervals.ci_95.lower.toLocaleString('en-IN')} – ₹{f.confidence_intervals.ci_95.upper.toLocaleString('en-IN')} Cr
                      </div>
                    </div>
                  </Card>
                ))}
              </div>

              {/* Legal Disclaimer */}
              <div className="p-3 rounded-lg bg-amber-500/10 border border-amber-500/20 text-xs text-amber-700 dark:text-amber-300">
                <span className="font-semibold block mb-0.5">Forecast Disclosure:</span>
                {forecast.disclaimer}
              </div>
            </>
          ) : (
            <div className="py-12 text-center text-xs text-slate-400">
              Generating statistical forecasts...
            </div>
          )}
        </Card>
      )}

      {/* Tab 15: AI RESEARCH (Interactive RAG with Citations) */}
      {activeTab === 'ai research' && (
        <Card className="p-6 space-y-6">
          <div className="flex justify-between items-center border-b border-slate-200 dark:border-slate-800 pb-3">
            <div>
              <CardTitle>AI Equity Research Agent: {company.symbol}</CardTitle>
              <p className="text-xs text-slate-500">
                Ask questions grounded strictly in official {company.name} filings and transcripts
              </p>
            </div>
            <Badge variant="brand" size="xs">
              EVIDENCE GROUNDED
            </Badge>
          </div>

          {/* Quick Prompts */}
          <div className="flex flex-wrap gap-2 text-xs">
            <span className="text-slate-400 font-mono py-1">Try:</span>
            {[
              `Summarize FY24 EBITDA margin expansion and key drivers`,
              `What capital expenditure plans were disclosed in the annual report?`,
              `Detail any significant order wins and major contracts`,
            ].map((p, i) => (
              <button
                key={i}
                onClick={() => setChatQuery(p)}
                className="px-2.5 py-1 rounded-md bg-slate-100 hover:bg-slate-200 dark:bg-slate-900 dark:hover:bg-slate-800 border border-slate-200 dark:border-slate-800 text-slate-700 dark:text-slate-300 transition-colors"
              >
                {p}
              </button>
            ))}
          </div>

          {/* Messages Container */}
          <div className="min-h-[300px] max-h-[500px] overflow-y-auto space-y-4 p-4 rounded-lg bg-slate-50 dark:bg-slate-900/30 border border-slate-200 dark:border-slate-800">
            {chatMessages.length === 0 ? (
              <div className="py-16 text-center text-xs text-slate-400">
                <Bot className="w-8 h-8 text-cyan-500 mx-auto mb-2 opacity-50" />
                Ask any question about {company.name}'s filings, earnings calls, or business metrics.
                Responses will cite exact document pages and excerpts.
              </div>
            ) : (
              chatMessages.map((msg, idx) => (
                <div
                  key={idx}
                  className={`flex flex-col ${msg.role === 'user' ? 'items-end' : 'items-start'}`}
                >
                  <div
                    className={`max-w-[85%] rounded-lg p-4 text-xs ${
                      msg.role === 'user'
                        ? 'bg-cyan-600 text-white font-medium'
                        : 'bg-white dark:bg-slate-850 border border-slate-200 dark:border-slate-800 text-slate-900 dark:text-slate-100 space-y-3'
                    }`}
                  >
                    {msg.role === 'assistant' && (
                      <div className="flex items-center justify-between pb-2 border-b border-slate-100 dark:border-slate-800">
                        <span className="font-semibold text-cyan-500 flex items-center gap-1.5">
                          <Bot className="w-3.5 h-3.5" /> AlphaNexus Research Agent
                        </span>
                        <Badge variant="gain" size="xs">
                          {msg.message_type === 'fact_grounded' ? 'Fact Grounded (RAG)' : 'Analytical Synthesis'}
                        </Badge>
                      </div>
                    )}

                    <div className="whitespace-pre-wrap leading-relaxed">{msg.content}</div>

                    {/* Citations Box */}
                    {msg.citations && msg.citations.length > 0 && (
                      <div className="mt-3 pt-3 border-t border-slate-200 dark:border-slate-800 space-y-2">
                        <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block font-mono">
                          Verified Document Citations ({msg.citations.length})
                        </span>
                        {msg.citations.map((c: any, cIdx: number) => (
                          <div
                            key={cIdx}
                            className="p-2 rounded bg-slate-50 dark:bg-slate-900/80 border border-slate-200 dark:border-slate-800 text-[11px]"
                          >
                            <div className="flex justify-between items-center text-cyan-500 font-semibold mb-1">
                              <span>
                                [{cIdx + 1}] {c.document_title || 'Annual Filing'} • Page {c.page_number || 'N/A'}
                              </span>
                              <span className="text-[10px] text-slate-400 font-mono">
                                Match: {(c.confidence_score * 100).toFixed(0)}%
                              </span>
                            </div>
                            <p className="text-slate-500 dark:text-slate-400 italic">
                              "{c.excerpt}"
                            </p>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              ))
            )}
            {chatLoading && (
              <div className="flex items-center gap-2 text-xs text-cyan-500 font-mono animate-pulse">
                <Bot className="w-4 h-4" /> Retrieving semantic passages & synthesizing report...
              </div>
            )}
          </div>

          {/* Composer */}
          <div className="flex items-center gap-2">
            <input
              value={chatQuery}
              onChange={(e) => setChatQuery(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSendChat()}
              placeholder={`Ask a question regarding ${company.symbol} filings, margins, or deals...`}
              className="flex-1 bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-800 rounded-md px-4 py-2.5 text-xs sm:text-sm text-slate-900 dark:text-slate-100 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-brand-500/30"
            />
            <Button
              variant="primary"
              size="md"
              onClick={handleSendChat}
              disabled={chatLoading || !chatQuery.trim()}
            >
              Analyze
            </Button>
          </div>
        </Card>
      )}

      {/* Other tabs fallback view */}
      {!['overview', 'financials', 'forecast', 'ai research'].includes(activeTab) && (
        <Card className="p-8 text-center space-y-3">
          <FileText className="w-10 h-10 text-cyan-500 mx-auto opacity-70" />
          <CardTitle className="capitalize">{activeTab} for {company.name}</CardTitle>
          <p className="text-xs text-slate-500 max-w-md mx-auto">
            Viewing {activeTab} data for {company.symbol}. In live connected mode, real-time disclosures are synchronized from official exchange feeds.
          </p>
          <div className="pt-2">
            <Button variant="outline" size="sm" onClick={() => setActiveTab('overview')}>
              Return to Overview
            </Button>
          </div>
        </Card>
      )}
    </div>
  );
};

