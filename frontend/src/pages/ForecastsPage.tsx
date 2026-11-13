import React, { useState, useEffect } from 'react';
import { motion } from 'motion/react';
import { TrendingUp, AlertTriangle } from 'lucide-react';
import {
  ComposedChart, Area, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceLine, Legend,
} from 'recharts';
import { ANButton } from '../components/shared/ANButton';
import { UniversalCompanySelector } from '../components/shared/UniversalCompanySelector';
import { useCompanyStore } from '../stores/companyStore';
import { api } from '../services/api';
import type { Company, ForecastResponseData } from '../types';

const METRICS = ['revenue', 'net_profit', 'ebitda', 'eps'];

export const ForecastsPage: React.FC = () => {
  const { selectedCompany, setSelectedCompany } = useCompanyStore();
  const [metric,    setMetric]    = useState('revenue');
  const [forecast,  setForecast]  = useState<ForecastResponseData | null>(null);
  const [loading,   setLoading]   = useState(false);
  const [generating, setGenerating] = useState(false);

  useEffect(() => {
    if (!selectedCompany) {
      api.getCompanies().then((d) => {
        if (d.length) setSelectedCompany(d[0]);
      });
    }
  }, []);

  useEffect(() => {
    if (!selectedCompany?.id) return;
    setLoading(true);
    api.getForecasts(selectedCompany.id, metric).then(setForecast).catch(() => setForecast(null)).finally(() => setLoading(false));
  }, [selectedCompany?.id, metric]);

  const generate = async () => {
    if (!selectedCompany?.id) return;
    setGenerating(true);
    try {
      const res = await api.generateForecast(selectedCompany.id, { metric_name: metric, forecast_horizon_years: 3 });
      setForecast(res);
    } finally { setGenerating(false); }
  };

  // Build chart data combining historical + forecasts
  const chartData = [
    ...(forecast?.historical ?? []).map((h) => ({
      period: h.period, actual: h.value, base: null, bullish: null, bearish: null,
    })),
    ...(forecast?.forecasts ?? []).map((f) => ({
      period: f.period, actual: null, base: f.base, bullish: f.bullish, bearish: f.bearish,
    })),
  ];

  return (
    <div className="page-container py-8 space-y-7">
      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
        <h1 className="text-3xl font-black tracking-tight" style={{ color: 'var(--text-1)', letterSpacing: '-0.02em' }}>
          Performance <span style={{ color: 'var(--brand)' }}>Forecasts</span>
        </h1>
        <p className="text-sm mt-1" style={{ color: 'var(--text-3)' }}>
          Statistical scenario modeling based on verified historical financials.
        </p>
      </motion.div>

      {/* Disclaimer */}
      <div className="flex items-start gap-3 p-4 rounded-xl"
        style={{ background: 'rgba(251,191,36,.06)', border: '1px solid rgba(251,191,36,.2)' }}>
        <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" style={{ color: 'var(--warning)' }} />
        <p className="text-xs leading-relaxed" style={{ color: 'var(--text-2)' }}>
          <strong style={{ color: 'var(--warning)' }}>Important:</strong>{' '}
          Forecasts are statistical estimates based on historical filings only. They are not investment advice
          and do not constitute a guarantee of future performance. All scenarios are illustrative.
        </p>
      </div>

      {/* Controls */}
      <div className="flex flex-wrap gap-3 items-center">
        <UniversalCompanySelector className="w-80" />
        <div className="flex gap-1.5">
          {METRICS.map((m) => (
            <button
              key={m}
              onClick={() => setMetric(m)}
              className="px-3 py-1.5 rounded-lg text-xs font-bold transition-all capitalize"
              style={{
                background: metric === m ? 'var(--brand)' : 'var(--surface-2)',
                color: metric === m ? '#fff' : 'var(--text-3)',
                border: `1px solid ${metric === m ? 'var(--brand)' : 'var(--border)'}`,
              }}
            >
              {m.replace('_', ' ')}
            </button>
          ))}
        </div>
        <ANButton variant="ghost" size="sm" loading={generating} onClick={generate}>
          Generate Forecast
        </ANButton>
      </div>

      {/* Chart */}
      <div className="card p-6 space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="font-bold" style={{ color: 'var(--text-1)' }}>
            {selectedCompany?.symbol} · {metric.replace('_', ' ').toUpperCase()} Forecast
          </h3>
          {forecast?.forecasts?.length === 0 && (
            <span className="badge badge-muted">No forecast data — click Generate</span>
          )}
        </div>

        {loading ? (
          <div className="skeleton h-64 rounded-xl" />
        ) : chartData.length === 0 ? (
          <div className="h-64 flex items-center justify-center text-sm" style={{ color: 'var(--text-4)' }}>
            Click "Generate Forecast" to run the statistical model.
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={280}>
            <ComposedChart data={chartData} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
              <defs>
                <linearGradient id="actualGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%"  stopColor="#1558C9" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#1558C9" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 6" stroke="var(--border)" />
              <XAxis dataKey="period" tick={{ fill: 'var(--text-4)', fontSize: 10 }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fill: 'var(--text-4)', fontSize: 10 }} axisLine={false} tickLine={false} width={65}
                tickFormatter={(v) => v >= 1000 ? `${(v/1000).toFixed(0)}K` : String(v)} />
              <Tooltip contentStyle={{ background: 'var(--surface-3)', border: '1px solid var(--border)', borderRadius: 10, fontSize: 11 }} />
              <Legend iconType="circle" wrapperStyle={{ fontSize: 11 }} />
              {/* Actual */}
              <Area type="monotone" dataKey="actual" stroke="#1558C9" strokeWidth={2.5}
                fill="url(#actualGrad)" dot={{ fill: '#1558C9', r: 4 }} name="Actual" connectNulls />
              {/* Forecast scenarios */}
              <Bar dataKey="bullish" fill="rgba(212,255,36,0.5)" radius={[4,4,0,0]} name="Bullish" />
              <Bar dataKey="base"    fill="rgba(21,88,201,0.6)"  radius={[4,4,0,0]} name="Base" />
              <Bar dataKey="bearish" fill="rgba(255,100,110,0.4)" radius={[4,4,0,0]} name="Bearish" />
            </ComposedChart>
          </ResponsiveContainer>
        )}

        {forecast?.disclaimer && (
          <div className="text-[10px] text-center" style={{ color: 'var(--text-4)' }}>
            {forecast.disclaimer}
          </div>
        )}
      </div>

      {/* Evaluation metrics */}
      {forecast?.evaluation && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {[
            { label: 'MAE',  value: forecast.evaluation.mae?.toFixed(2) ?? '—' },
            { label: 'RMSE', value: forecast.evaluation.rmse?.toFixed(2) ?? '—' },
            { label: 'MAPE', value: forecast.evaluation.mape != null ? `${forecast.evaluation.mape.toFixed(1)}%` : '—' },
            { label: 'Directional', value: forecast.evaluation.directional_accuracy != null ? `${(forecast.evaluation.directional_accuracy*100).toFixed(0)}%` : '—' },
          ].map((m) => (
            <div key={m.label} className="card p-4 text-center">
              <div className="text-[10px] font-bold uppercase tracking-wider mb-1" style={{ color: 'var(--text-4)' }}>{m.label}</div>
              <div className="text-lg font-black font-tabular" style={{ color: 'var(--text-1)' }}>{m.value}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
