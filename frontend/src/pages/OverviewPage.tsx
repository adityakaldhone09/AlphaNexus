import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { motion } from 'motion/react';
import {
  ArrowUpRight, TrendingUp, TrendingDown, Bot, Zap,
  FileText, Briefcase, AlertTriangle, Building2, BarChart2,
} from 'lucide-react';
import { AnimatedCandlesticks } from '../components/charts/AnimatedCandlesticks';
import { ANCard, KPICard } from '../components/shared/ANCard';
import { ANButton } from '../components/shared/ANButton';
import { Logo } from '../components/brand/Logo';
import { api } from '../services/api';
import type { Company, NewsArticle, MarketEvent } from '../types';

// ── Sparkline mini-component ──
const Spark: React.FC<{ up: boolean }> = ({ up }) => (
  <svg viewBox="0 0 60 24" className="w-14 h-6" fill="none">
    {up
      ? <polyline points="0,20 12,16 24,18 36,8 48,12 60,4" stroke="var(--positive-text)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
      : <polyline points="0,4 12,8 24,6 36,16 48,12 60,20" stroke="var(--negative-text)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
    }
  </svg>
);

// ── Index data (live integration pending — DhanHQ) ──
const INDICES = [
  { name: 'NIFTY 50',   value: '24,530.90', change: '+142.80', pct: '+0.59%', up: true,  source: 'NSE' },
  { name: 'SENSEX',     value: '80,436.84', change: '+486.25', pct: '+0.61%', up: true,  source: 'BSE' },
  { name: 'NIFTY BANK', value: '52,190.20', change: '+382.40', pct: '+0.74%', up: true,  source: 'NSE' },
  { name: 'INDIA VIX',  value: '13.42',     change: '-0.45',   pct: '-3.25%', up: false, source: 'NSE' },
];

export const OverviewPage: React.FC = () => {
  const [companies, setCompanies]  = useState<Company[]>([]);
  const [news, setNews]            = useState<NewsArticle[]>([]);
  const [events, setEvents]        = useState<MarketEvent[]>([]);
  const [loading, setLoading]      = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const [comps, newsData, eventsData] = await Promise.all([
          api.getCompanies(),
          api.getNews(),
          api.getMarketEvents(),
        ]);
        setCompanies(comps);
        setNews(newsData.slice(0, 5));
        setEvents(eventsData.slice(0, 5));
      } catch (e) {
        console.error('Dashboard load error:', e);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  return (
    <div className="page-container py-8 space-y-10">

      {/* ── HERO ───────────────────────────────────────────── */}
      <section className="relative overflow-hidden rounded-3xl px-8 py-10 md:py-14"
        style={{ background: 'var(--surface-1)', border: '1px solid var(--border)' }}>
        {/* Brand glow */}
        <div className="absolute -top-24 -right-24 w-96 h-96 rounded-full pointer-events-none"
          style={{ background: 'radial-gradient(circle, rgba(21,88,201,0.12) 0%, transparent 70%)' }} />
        <div className="absolute -bottom-16 left-0 w-64 h-64 rounded-full pointer-events-none"
          style={{ background: 'radial-gradient(circle, rgba(212,255,36,0.06) 0%, transparent 70%)' }} />

        <div className="relative grid md:grid-cols-2 gap-8 items-center">
          <div className="space-y-5">
            <motion.div
              initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5 }}
            >
              <div
                className="inline-flex items-center gap-2 mb-3.5 px-3 py-1 rounded-full text-xs font-semibold backdrop-blur-sm"
                style={{
                  background: 'var(--brand-muted)',
                  color: 'var(--brand)',
                  border: '1px solid var(--border)',
                }}
              >
                <Logo variant="icon" height={16} />
                <span>AI Financial Intelligence Platform</span>
              </div>
              <h1 className="text-4xl md:text-5xl font-black tracking-tight leading-none"
                style={{ color: 'var(--text-1)', letterSpacing: '-0.03em' }}>
                See Beyond the<br />
                <span style={{ color: 'var(--brand)' }}>Stock Price.</span>
              </h1>
              <p className="mt-4 text-base leading-relaxed" style={{ color: 'var(--text-2)' }}>
                Evidence-backed equity research powered by AI, pgvector RAG, and
                verified corporate filings from NSE / BSE listed companies.
              </p>
            </motion.div>

            <motion.div
              className="flex flex-wrap gap-3"
              initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.2, duration: 0.4 }}
            >
              <Link to="/research">
                <ANButton variant="brand" size="md" icon={<Bot className="w-4 h-4" />}>
                  Start AI Research
                </ANButton>
              </Link>
              <Link to="/discover">
                <ANButton variant="ghost" size="md" icon={<Building2 className="w-4 h-4" />}>
                  Explore Companies
                </ANButton>
              </Link>
            </motion.div>

            <motion.div
              className="flex gap-6 pt-2"
              initial={{ opacity: 0 }} animate={{ opacity: 1 }}
              transition={{ delay: 0.4, duration: 0.5 }}
            >
              {[
                { label: 'Companies', value: companies.length || '5+' },
                { label: 'RAG Chunks', value: '—' },
                { label: 'AI Engine', value: 'Live' },
              ].map((s) => (
                <div key={s.label}>
                  <div className="text-xl font-black font-tabular" style={{ color: 'var(--lime)' }}>{s.value}</div>
                  <div className="text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--text-4)' }}>{s.label}</div>
                </div>
              ))}
            </motion.div>
          </div>

          {/* Animated Chart */}
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: 0.1, duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
            className="hidden md:block"
          >
            <AnimatedCandlesticks />
          </motion.div>
        </div>
      </section>

      {/* ── MARKET INDICES ─────────────────────────────────── */}
      <section>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-bold uppercase tracking-widest" style={{ color: 'var(--text-3)' }}>
            Market Overview
          </h2>
          <span className="badge badge-muted">Live integration: DhanHQ pending</span>
        </div>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          {INDICES.map((idx, i) => (
            <motion.div
              key={idx.name}
              className="card p-4"
              initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.07 }}
            >
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-bold uppercase tracking-wider" style={{ color: 'var(--text-4)' }}>
                  {idx.source}
                </span>
                <Spark up={idx.up} />
              </div>
              <div className="text-sm font-black" style={{ color: 'var(--text-1)' }}>{idx.name}</div>
              <div className="text-xl font-black font-tabular mt-0.5" style={{ color: 'var(--text-1)' }}>
                {idx.value}
              </div>
              <div className="text-xs font-semibold font-tabular mt-1 flex items-center gap-1"
                style={{ color: idx.up ? 'var(--positive-text)' : 'var(--negative-text)' }}>
                {idx.up ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
                {idx.change} ({idx.pct})
              </div>
            </motion.div>
          ))}
        </div>
      </section>

      {/* ── COMPANIES TABLE + INTELLIGENCE FEED ─────────────── */}
      <div className="grid lg:grid-cols-3 gap-6">
        {/* Companies */}
        <div className="lg:col-span-2 card overflow-hidden">
          <div className="flex items-center justify-between p-5" style={{ borderBottom: '1px solid var(--border)' }}>
            <h3 className="font-bold" style={{ color: 'var(--text-1)' }}>NSE / BSE Market Leaders</h3>
            <Link to="/discover">
              <ANButton variant="ghost" size="xs" icon={<ArrowUpRight className="w-3.5 h-3.5" />} iconRight>
                All Companies
              </ANButton>
            </Link>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead style={{ background: 'var(--surface-2)' }}>
                <tr className="text-[10px] font-bold uppercase tracking-wider" style={{ color: 'var(--text-4)' }}>
                  {['Symbol', 'Company', 'LTP ₹', 'Change', 'P/E', 'ROE', ''].map((h) => (
                    <th key={h} className="px-4 py-2.5 font-bold">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {loading
                  ? Array.from({ length: 4 }).map((_, i) => (
                      <tr key={i} style={{ borderTop: '1px solid var(--border)' }}>
                        {Array.from({ length: 7 }).map((_, j) => (
                          <td key={j} className="px-4 py-3"><div className="skeleton h-3 w-16 rounded" /></td>
                        ))}
                      </tr>
                    ))
                  : companies.map((c) => (
                      <tr key={c.id}
                        className="transition-colors hover:bg-[var(--surface-2)]"
                        style={{ borderTop: '1px solid var(--border)' }}>
                        <td className="px-4 py-3">
                          <Link to={`/company/${c.symbol}`}
                            className="font-black font-mono text-xs hover:underline"
                            style={{ color: 'var(--brand)' }}>
                            {c.symbol}
                          </Link>
                        </td>
                        <td className="px-4 py-3 max-w-[160px] truncate font-medium text-xs" style={{ color: 'var(--text-2)' }}>
                          {c.name}
                        </td>
                        <td className="px-4 py-3 font-black font-tabular text-xs" style={{ color: 'var(--text-1)' }}>
                          {c.current_price ? `₹${c.current_price.toLocaleString('en-IN')}` : '—'}
                        </td>
                        <td className="px-4 py-3 font-semibold font-tabular text-xs"
                          style={{ color: (c.day_change_percent ?? 0) >= 0 ? 'var(--positive-text)' : 'var(--negative-text)' }}>
                          {c.day_change_percent != null
                            ? `${c.day_change_percent >= 0 ? '+' : ''}${c.day_change_percent}%`
                            : '—'}
                        </td>
                        <td className="px-4 py-3 text-xs" style={{ color: 'var(--text-3)' }}>{c.pe_ratio ?? '—'}</td>
                        <td className="px-4 py-3 text-xs" style={{ color: 'var(--text-3)' }}>
                          {c.roe != null ? `${c.roe}%` : '—'}
                        </td>
                        <td className="px-4 py-3">
                          <Link to={`/company/${c.symbol}`}>
                            <ANButton variant="ghost" size="xs">Research</ANButton>
                          </Link>
                        </td>
                      </tr>
                    ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Intelligence Feed */}
        <div className="card flex flex-col overflow-hidden">
          <div className="flex items-center justify-between p-5" style={{ borderBottom: '1px solid var(--border)' }}>
            <h3 className="font-bold flex items-center gap-2" style={{ color: 'var(--text-1)' }}>
              <Zap className="w-4 h-4" style={{ color: 'var(--lime)' }} />
              Intelligence Feed
            </h3>
            <Link to="/news">
              <ANButton variant="ghost" size="xs">View All</ANButton>
            </Link>
          </div>
          <div className="flex-1 overflow-y-auto p-3 space-y-2">
            {loading
              ? Array.from({ length: 4 }).map((_, i) => (
                  <div key={i} className="rounded-xl p-3" style={{ background: 'var(--surface-2)' }}>
                    <div className="skeleton h-2.5 w-20 rounded mb-2" />
                    <div className="skeleton h-3 w-full rounded mb-1" />
                    <div className="skeleton h-3 w-3/4 rounded" />
                  </div>
                ))
              : news.map((item) => (
                  <div key={item.id}
                    className="rounded-xl p-3 transition-colors hover:border-[var(--border-brand)] cursor-pointer"
                    style={{ background: 'var(--surface-2)', border: '1px solid var(--border)' }}>
                    <div className="flex items-center justify-between mb-1.5">
                      <span className="badge badge-brand">{item.category || 'Market'}</span>
                      <span className="text-[10px] font-mono" style={{ color: 'var(--text-4)' }}>
                        {new Date(item.published_at).toLocaleDateString('en-IN', { month: 'short', day: 'numeric' })}
                      </span>
                    </div>
                    <p className="text-xs font-semibold leading-snug line-clamp-2" style={{ color: 'var(--text-1)' }}>
                      {item.title}
                    </p>
                  </div>
                ))}
          </div>
        </div>
      </div>

      {/* ── AI INSIGHTS ───────────────────────────────────── */}
      <section>
        <div className="flex items-center gap-2 mb-4">
          <Bot className="w-4 h-4" style={{ color: 'var(--brand)' }} />
          <h2 className="font-bold" style={{ color: 'var(--text-1)' }}>AI Equity Insights</h2>
          <span className="badge badge-brand">Synthesis · Fact-Grounded</span>
        </div>
        <div className="grid md:grid-cols-3 gap-4">
          {[
            { icon: <TrendingUp className="w-4 h-4" />, company: 'RELIANCE', label: 'Capex Acceleration',
              text: 'SECI 10 GWh battery storage win initiates commercial scaling for Jamnagar new energy giga-factories.' },
            { icon: <Zap className="w-4 h-4" />, company: 'TCS', label: 'Margin Resilience',
              text: 'Operating margin holds at 24.6% (+50 bps) driven by subcontractor rationalization and $42.7B TCV.' },
            { icon: <AlertTriangle className="w-4 h-4" />, company: 'HDFCBANK', label: 'LDR Watch',
              text: 'Deposit growth outpaced loans by 300 bps in Q3; monitoring progress toward 85% post-merger LDR.' },
          ].map((ins, i) => (
            <motion.div
              key={ins.company}
              className="rounded-xl p-4 space-y-2"
              style={{
                background: 'var(--surface-1)',
                border: '1px solid var(--border)',
              }}
              initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.1 * i }}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 text-xs font-bold" style={{ color: 'var(--brand)' }}>
                  {ins.icon} {ins.label}
                </div>
                <span className="font-black font-mono text-xs" style={{ color: 'var(--text-3)' }}>{ins.company}</span>
              </div>
              <p className="text-xs leading-relaxed" style={{ color: 'var(--text-2)' }}>{ins.text}</p>
            </motion.div>
          ))}
        </div>
      </section>

    </div>
  );
};
