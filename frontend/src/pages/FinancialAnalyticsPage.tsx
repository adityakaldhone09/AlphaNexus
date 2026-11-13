import React, { useState, useEffect } from 'react';
import { motion } from 'motion/react';
import { BarChart2, TrendingUp, Building2 } from 'lucide-react';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, LineChart, Line, Area, AreaChart, Legend,
} from 'recharts';
import { ANButton } from '../components/shared/ANButton';
import { UniversalCompanySelector } from '../components/shared/UniversalCompanySelector';
import { useCompanyStore } from '../stores/companyStore';
import { api } from '../services/api';
import type { Company, FinancialMetric } from '../types';

const METRICS = ['revenue', 'ebitda', 'net_profit', 'eps'];

const CustomTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-xl px-4 py-3 text-xs"
      style={{ background: 'var(--surface-3)', border: '1px solid var(--border)', color: 'var(--text-1)' }}>
      <div className="font-bold mb-1" style={{ color: 'var(--text-2)' }}>{label}</div>
      {payload.map((p: any) => (
        <div key={p.name} className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full" style={{ background: p.color }} />
          <span style={{ color: 'var(--text-2)' }}>{p.name}:</span>
          <span className="font-black font-tabular">{p.value?.toLocaleString('en-IN')}</span>
        </div>
      ))}
    </div>
  );
};

export const FinancialAnalyticsPage: React.FC = () => {
  const [companies,  setCompanies]  = useState<Company[]>([]);
  const { selectedCompany, setSelectedCompany } = useCompanyStore();
  const [metrics,    setMetrics]    = useState<FinancialMetric[]>([]);
  const [ratios,     setRatios]     = useState<Record<string, any>>({});
  const [loading,    setLoading]    = useState(false);
  const [activeMetric, setActiveMetric] = useState('revenue');

  useEffect(() => {
    if (!selectedCompany) {
      api.getCompanies().then((d) => {
        setCompanies(d);
        if (d.length) setSelectedCompany(d[0]);
      });
    } else {
      api.getCompanies().then(setCompanies);
    }
  }, []);

  useEffect(() => {
    if (!selectedCompany?.id) return;
    setLoading(true);
    Promise.all([
      api.getCompanyFinancials(selectedCompany.id),
      api.getCompanyRatios(selectedCompany.id),
    ]).then(([m, r]) => {
      setMetrics(m);
      setRatios(r.computed_metrics ?? {});
    }).finally(() => setLoading(false));
  }, [selectedCompany?.id]);

  // Build chart data for active metric
  const chartData = metrics
    .filter((m) => m.metric_name === activeMetric)
    .sort((a, b) => a.financial_year.localeCompare(b.financial_year))
    .map((m) => ({ fy: m.financial_year, value: m.value, unit: m.unit }));

  const ratioItems = [
    { key: 'ebitda_margin',         label: 'EBITDA Margin',    suffix: '%' },
    { key: 'net_profit_margin',     label: 'Net Margin',       suffix: '%' },
    { key: 'roe',                   label: 'ROE',              suffix: '%' },
    { key: 'roce',                  label: 'ROCE',             suffix: '%' },
    { key: 'revenue_growth_yoy',    label: 'Rev Growth YoY',   suffix: '%' },
    { key: 'net_profit_growth_yoy', label: 'PAT Growth YoY',   suffix: '%' },
    { key: 'pe_ratio',              label: 'P/E Ratio',        suffix: 'x' },
    { key: 'pb_ratio',              label: 'P/B Ratio',        suffix: 'x' },
  ];

  return (
    <div className="page-container py-8 space-y-7">
      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
        <h1 className="text-3xl font-black tracking-tight" style={{ color: 'var(--text-1)', letterSpacing: '-0.02em' }}>
          Financial <span style={{ color: 'var(--brand)' }}>Analytics</span>
        </h1>
        <p className="text-sm mt-1" style={{ color: 'var(--text-3)' }}>
          Multi-year financial performance, ratios and trend analysis.
        </p>
      </motion.div>

      {/* Universal Company Selector */}
      <div className="max-w-md">
        <UniversalCompanySelector
          placeholder="Select or search any Indian equity..."
        />
      </div>

      {/* KPIs */}
      {selectedCompany && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {[
            { label: 'Current Price', value: selectedCompany.current_price ? `₹${selectedCompany.current_price.toLocaleString('en-IN')}` : '—' },
            { label: 'Market Cap', value: selectedCompany.market_cap ? `₹${(selectedCompany.market_cap/1000).toFixed(0)}K Cr` : '—' },
            { label: 'P/E Ratio', value: selectedCompany.pe_ratio ? `${selectedCompany.pe_ratio}x` : '—' },
            { label: 'ROE', value: selectedCompany.roe ? `${selectedCompany.roe}%` : '—' },
          ].map((k, i) => (
            <motion.div key={k.label} className="card p-4"
              initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.06 }}>
              <div className="text-[10px] font-bold uppercase tracking-wider mb-1.5" style={{ color: 'var(--text-4)' }}>{k.label}</div>
              <div className="text-xl font-black font-tabular" style={{ color: 'var(--text-1)' }}>{k.value}</div>
            </motion.div>
          ))}
        </div>
      )}

      {/* Chart + Ratios */}
      <div className="grid lg:grid-cols-3 gap-6">
        {/* Chart */}
        <div className="lg:col-span-2 card p-5 space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h3 className="font-bold" style={{ color: 'var(--text-1)' }}>
              {selectedCompany?.symbol} · Historical Performance
            </h3>
            <div className="flex gap-1.5 flex-wrap">
              {METRICS.map((m) => (
                <button
                  key={m}
                  onClick={() => setActiveMetric(m)}
                  className="px-2.5 py-1 rounded-md text-[11px] font-bold uppercase tracking-wide transition-all"
                  style={{
                    background: activeMetric === m ? 'var(--brand-muted)' : 'var(--surface-2)',
                    color: activeMetric === m ? 'var(--brand)' : 'var(--text-3)',
                    border: `1px solid ${activeMetric === m ? 'var(--border-brand)' : 'var(--border)'}`,
                  }}
                >
                  {m.replace('_', ' ')}
                </button>
              ))}
            </div>
          </div>

          {loading ? (
            <div className="skeleton h-48 rounded-xl w-full" />
          ) : chartData.length === 0 ? (
            <div className="h-48 flex items-center justify-center text-sm" style={{ color: 'var(--text-4)' }}>
              No data available.
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={220}>
              <AreaChart data={chartData} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
                <defs>
                  <linearGradient id="metricGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%"  stopColor="#1558C9" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#1558C9" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 6" stroke="var(--border)" />
                <XAxis dataKey="fy" tick={{ fill: 'var(--text-4)', fontSize: 10 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: 'var(--text-4)', fontSize: 10 }} axisLine={false} tickLine={false} width={60}
                  tickFormatter={(v) => v >= 1000 ? `${(v/1000).toFixed(0)}K` : v} />
                <Tooltip content={<CustomTooltip />} />
                <Area type="monotone" dataKey="value" stroke="#1558C9" strokeWidth={2.5}
                  fill="url(#metricGrad)" dot={{ fill: '#1558C9', strokeWidth: 2, r: 4 }}
                  activeDot={{ r: 6, fill: 'var(--lime)' }} name={activeMetric} />
              </AreaChart>
            </ResponsiveContainer>
          )}
          {chartData.length > 0 && (
            <div className="text-[10px] text-center" style={{ color: 'var(--text-4)' }}>
              Unit: {chartData[0]?.unit || 'INR Crores'} · Source: Company Filings
            </div>
          )}
        </div>

        {/* Ratios Panel */}
        <div className="card p-5 space-y-4">
          <h3 className="font-bold text-sm" style={{ color: 'var(--text-1)' }}>Key Ratios</h3>
          {loading ? (
            <div className="space-y-3">{Array.from({ length: 6 }).map((_, i) => <div key={i} className="skeleton h-9 rounded-lg" />)}</div>
          ) : (
            <div className="space-y-2">
              {ratioItems.map((r) => {
                const val = ratios[r.key];
                const num = typeof val === 'number' ? val : null;
                return (
                  <div key={r.key} className="flex items-center justify-between p-2.5 rounded-lg"
                    style={{ background: 'var(--surface-2)' }}>
                    <span className="text-xs font-medium" style={{ color: 'var(--text-3)' }}>{r.label}</span>
                    <span className="text-xs font-black font-tabular" style={{ color: num != null ? 'var(--text-1)' : 'var(--text-4)' }}>
                      {num != null ? `${num.toFixed(1)}${r.suffix}` : '—'}
                    </span>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
